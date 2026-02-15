#!/usr/bin/env python3
"""
Flash Arbitrage Bot — Solana
Built by FORGE, NULL, RAZOR — no APIs, pure on-chain

Architecture:
1. Monitor price spreads across DEXs via DexScreener (free, no auth)
2. When spread > threshold, construct flash loan arb tx
3. Flash borrow via Marginfi → Swap DEX A → Swap DEX B → Repay

Current limitation: Jupiter API requires auth.
Workaround: Extract swap instructions from recent on-chain transactions.
"""

import json
import time
import struct
import subprocess
import urllib.request
from dataclasses import dataclass
from typing import Optional, List, Dict

# === CONFIG ===
WALLET = "EXEDJvuAaYt9yN5mwZRPdCP19tYuF6LWztnu6qpbepTq"
BONK_MINT = "DezXAZ8z7PnrnRJjz3wXBoRgixCa6xjnB7YaB1pPB263"
SOL_MINT = "So11111111111111111111111111111111111111112"
USDC_MINT = "EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v"

# Meteora DLMM pool we decoded
METEORA_BONK_SOL = {
    "address": "6Qmm15WNFfA5MhAxknsQjmxX2kGqb8H3qCoZwfWVxRNB",
    "program": "LBUZKhRxPF3XUpBCjp4YzTKgLccjZhTSDM9YuVaPwxo",
    "reserve_x": "13grxnxkeiyVBycg6R2w8RqXxM16rLnA8awuMFf6YMPH",  # BONK
    "reserve_y": "8o3V6AYjnPRoZkPKLYmxPXv2EgZ5bfC8M5UyzJcso3Yj",  # wSOL
    "oracle": "H4aPFEMHmPUWCizkdbryj182TzXpiMs76SroK7xMdEVM",
    "active_id": -182,
    "bin_step": 400,
}

# Marginfi flash loan
MARGINFI_PROGRAM = "MFv2hWf31Z9kbCa1snEPYctwafyhdvnV7FZnsebVacA"
MARGINFI_BORROW_DISC = "0e8321dc51bab46b"
MARGINFI_REPAY_DISC = "4fd1acb1de33ad97"
MARGINFI_END_FL_DISC = "697cc96a9902089c"

# Thresholds
MIN_SPREAD_PCT = 1.0   # Minimum spread to attempt arb
MAX_TRADE_USD = 500    # Max trade size (limited by pool liquidity)
GAS_COST_SOL = 0.000029  # Typical gas per tx

class PriceScanner:
    """Scan prices across DEXs using DexScreener (free, no auth)"""
    
    def scan_token(self, mint: str) -> List[Dict]:
        """Get all pools for a token across DEXs"""
        url = f"https://api.dexscreener.com/latest/dex/tokens/{mint}"
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "FlashArbBot/1.0"})
            with urllib.request.urlopen(req, timeout=10) as resp:
                data = json.loads(resp.read())
            
            pools = []
            for p in data.get("pairs", []):
                if p.get("chainId") != "solana":
                    continue
                price = float(p.get("priceUsd", 0))
                liq = p.get("liquidity", {}).get("usd", 0)
                if price > 0 and liq > 10000:  # Filter noise
                    pools.append({
                        "dex": p["dexId"],
                        "price": price,
                        "liquidity": liq,
                        "pair": p["pairAddress"],
                        "base": p["baseToken"]["symbol"],
                        "quote": p["quoteToken"]["symbol"],
                    })
            return sorted(pools, key=lambda x: x["price"])
        except Exception as e:
            print(f"[SCAN ERROR] {e}")
            return []
    
    def find_arb(self, pools: List[Dict]) -> Optional[Dict]:
        """Find best arbitrage opportunity"""
        if len(pools) < 2:
            return None
        
        buy = pools[0]   # Cheapest
        sell = pools[-1]  # Most expensive
        
        spread_pct = (sell["price"] - buy["price"]) / buy["price"] * 100
        # Estimate fees: ~0.3% per swap × 2
        net_pct = spread_pct - 0.6
        
        if net_pct < MIN_SPREAD_PCT:
            return None
        
        # Limit by smaller pool liquidity
        max_size = min(buy["liquidity"], sell["liquidity"]) * 0.02  # 2% of pool
        trade_size = min(max_size, MAX_TRADE_USD)
        profit_usd = trade_size * net_pct / 100
        
        return {
            "buy_dex": buy["dex"],
            "buy_price": buy["price"],
            "buy_pool": buy["pair"],
            "sell_dex": sell["dex"],
            "sell_price": sell["price"],
            "sell_pool": sell["pair"],
            "spread_pct": spread_pct,
            "net_pct": net_pct,
            "trade_size": trade_size,
            "profit_usd": profit_usd,
        }

class OnChainReader:
    """Read on-chain data via Solana RPC"""
    
    RPC = "https://api.mainnet-beta.solana.com"
    
    def get_balance(self, address: str) -> float:
        """Get SOL balance"""
        try:
            result = subprocess.run(
                ["solana", "balance", address],
                capture_output=True, text=True, timeout=10,
                env={"PATH": f"/Users/invite/.local/share/solana/install/active_release/bin:{subprocess.os.environ.get('PATH','')}"}
            )
            return float(result.stdout.strip().split()[0])
        except:
            return 0.0
    
    def get_token_reserve(self, account: str) -> int:
        """Read token account balance (raw amount)"""
        payload = {
            "jsonrpc": "2.0", "id": 1,
            "method": "getAccountInfo",
            "params": [account, {"encoding": "base64"}]
        }
        try:
            req = urllib.request.Request(
                self.RPC,
                data=json.dumps(payload).encode(),
                headers={"Content-Type": "application/json"}
            )
            with urllib.request.urlopen(req, timeout=10) as resp:
                data = json.loads(resp.read())
            import base64
            raw = base64.b64decode(data["result"]["value"]["data"][0])
            return struct.unpack_from('<Q', raw, 64)[0]
        except Exception as e:
            print(f"[RPC ERROR] {e}")
            return 0

def main():
    scanner = PriceScanner()
    reader = OnChainReader()
    
    print("=" * 60)
    print("  FLASH ARB BOT — Solana")
    print(f"  Wallet: {WALLET}")
    print(f"  Balance: {reader.get_balance(WALLET)} SOL")
    print("=" * 60)
    
    # Scan BONK pools
    print("\n[SCANNING] BONK pools across DEXs...")
    pools = scanner.scan_token(BONK_MINT)
    
    if not pools:
        print("[ERROR] No pools found")
        return
    
    print(f"\n  Found {len(pools)} pools (liq > $10K):")
    for p in pools:
        print(f"    {p['dex']:12} ${p['price']:.10f}  liq=${p['liquidity']:>10,.0f}  {p['base']}/{p['quote']}")
    
    # Find arb
    arb = scanner.find_arb(pools)
    
    if arb:
        print(f"\n{'='*60}")
        print(f"  🎯 ARBITRAGE DETECTED!")
        print(f"  BUY:  {arb['buy_dex']:12} @ ${arb['buy_price']:.10f}")
        print(f"  SELL: {arb['sell_dex']:12} @ ${arb['sell_price']:.10f}")
        print(f"  Spread: {arb['spread_pct']:.2f}% | Net: {arb['net_pct']:.2f}%")
        print(f"  Trade size: ${arb['trade_size']:,.2f}")
        print(f"  Estimated profit: ${arb['profit_usd']:,.2f}")
        print(f"  Gas cost: ${GAS_COST_SOL * 90.13:.4f}")
        print(f"{'='*60}")
        
        # Read on-chain reserves to verify
        print("\n[VERIFYING] On-chain pool reserves...")
        bonk_reserve = reader.get_token_reserve(METEORA_BONK_SOL["reserve_x"])
        sol_reserve = reader.get_token_reserve(METEORA_BONK_SOL["reserve_y"])
        print(f"  Meteora BONK reserve: {bonk_reserve / 10**5:,.2f} BONK")
        print(f"  Meteora SOL reserve:  {sol_reserve / 10**9:.6f} SOL (${sol_reserve / 10**9 * 90.13:.2f})")
        
        print("\n[STATUS] Flash loan execution not yet implemented")
        print("  Missing: Jupiter swap instruction builder (API locked)")
        print("  Workaround in progress: tx template extraction from on-chain data")
    else:
        print(f"\n  No arb found (min spread: {MIN_SPREAD_PCT}%)")
        best_spread = 0
        if len(pools) >= 2:
            best_spread = (pools[-1]["price"] - pools[0]["price"]) / pools[0]["price"] * 100
        print(f"  Best spread: {best_spread:.2f}% (need > {MIN_SPREAD_PCT + 0.6:.1f}% gross)")

if __name__ == "__main__":
    main()
