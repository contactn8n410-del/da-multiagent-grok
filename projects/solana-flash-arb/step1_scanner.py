#!/usr/bin/env python3
"""
Step 1: Real-time price scanner across Solana DEXes.
Finds arbitrage opportunities between Raydium, Orca, and other pools.
Zero capital needed - just reads on-chain data.
"""

import json
import time
import requests
from dataclasses import dataclass

# Major Solana token mints
TOKENS = {
    "SOL": "So11111111111111111111111111111111111111112",
    "USDC": "EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v",
    "USDT": "Es9vMFrzaCERmJfrF4H2FYD4KCoNkY11McCe8BenwNYB",
    "RAY": "4k3Dyjzvzp8eMZWUXbBCjEvwSkkk59S5iCNLY3QrkX6R",
    "ORCA": "orcaEKTdK7LKz57vaAYr9QeNsVEPfiu6QeMU1kektZE",
    "mSOL": "mSoLzYCxHdYgdzU16g5QSh3i5K3z3KZK7ytfqcJm7So",
    "JUP": "JUPyiwrYJFskUPiHa7hkeR8VUtAeFoSYbKedZNsDvCN",
    "BONK": "DezXAZ8z7PnrnRJjz3wXBoRgixCa6xjnB7YaB1pPB263",
}

RPC = "https://api.mainnet-beta.solana.com"

@dataclass
class PoolPrice:
    dex: str
    pair: str
    price: float
    liquidity_usd: float
    pool_address: str

def get_raydium_pools():
    """Fetch Raydium pool data via their API"""
    try:
        resp = requests.get(
            "https://api-v3.raydium.io/pools/info/list?poolType=standard&poolSortField=liquidity&sortType=desc&pageSize=20&page=1",
            timeout=10
        )
        if resp.status_code == 200:
            data = resp.json()
            pools = []
            for pool in data.get("data", {}).get("data", []):
                pools.append({
                    "id": pool.get("id"),
                    "mintA": pool.get("mintA", {}).get("symbol", "?"),
                    "mintB": pool.get("mintB", {}).get("symbol", "?"),
                    "price": pool.get("price", 0),
                    "tvl": pool.get("tvl", 0),
                })
            return pools
    except Exception as e:
        print(f"Raydium API error: {e}")
    return []

def get_dexscreener_prices(token_address):
    """Get prices across all DEXes via DexScreener"""
    try:
        resp = requests.get(
            f"https://api.dexscreener.com/latest/dex/tokens/{token_address}",
            timeout=10
        )
        if resp.status_code == 200:
            data = resp.json()
            prices = []
            for pair in data.get("pairs", [])[:10]:
                prices.append(PoolPrice(
                    dex=pair.get("dexId", "?"),
                    pair=f"{pair.get('baseToken',{}).get('symbol','?')}/{pair.get('quoteToken',{}).get('symbol','?')}",
                    price=float(pair.get("priceUsd", 0)),
                    liquidity_usd=float(pair.get("liquidity", {}).get("usd", 0)),
                    pool_address=pair.get("pairAddress", ""),
                ))
            return prices
    except Exception as e:
        print(f"DexScreener error: {e}")
    return []

def find_arbitrage(prices: list[PoolPrice], min_spread_pct=0.3):
    """Find price discrepancies between DEXes"""
    if len(prices) < 2:
        return []
    
    opps = []
    for i, p1 in enumerate(prices):
        for p2 in prices[i+1:]:
            if p1.price <= 0 or p2.price <= 0:
                continue
            if p1.liquidity_usd < 1000 or p2.liquidity_usd < 1000:
                continue  # Skip illiquid pools
            
            spread = abs(p1.price - p2.price) / min(p1.price, p2.price) * 100
            if spread >= min_spread_pct:
                buy_pool = p1 if p1.price < p2.price else p2
                sell_pool = p2 if p1.price < p2.price else p1
                
                # Estimate profit for 1 SOL trade
                profit_pct = spread - 0.6  # Subtract ~0.3% fee per swap × 2
                if profit_pct > 0:
                    opps.append({
                        "pair": p1.pair,
                        "buy_dex": buy_pool.dex,
                        "buy_price": buy_pool.price,
                        "sell_dex": sell_pool.dex,
                        "sell_price": sell_pool.price,
                        "spread_pct": spread,
                        "net_profit_pct": profit_pct,
                        "buy_liq": buy_pool.liquidity_usd,
                        "sell_liq": sell_pool.liquidity_usd,
                    })
    
    return sorted(opps, key=lambda x: x["net_profit_pct"], reverse=True)

def scan_token(name, address):
    """Scan a single token for arb opportunities"""
    prices = get_dexscreener_prices(address)
    if not prices:
        return []
    
    # Group by base pair
    sol_prices = [p for p in prices if "SOL" in p.pair or "USDC" in p.pair]
    opps = find_arbitrage(sol_prices)
    
    if opps:
        print(f"\n🔥 {name} — {len(opps)} opportunities found:")
        for opp in opps[:3]:
            print(f"   Buy on {opp['buy_dex']:12s} @ ${opp['buy_price']:.6f}")
            print(f"   Sell on {opp['sell_dex']:12s} @ ${opp['sell_price']:.6f}")
            print(f"   Spread: {opp['spread_pct']:.2f}% | Net: {opp['net_profit_pct']:.2f}%")
            print(f"   Liquidity: ${opp['buy_liq']:,.0f} / ${opp['sell_liq']:,.0f}")
            print()
    
    return opps

def main():
    print("=" * 60)
    print("  SOLANA ARB SCANNER — Real-time cross-DEX price monitor")
    print("=" * 60)
    
    cycle = 0
    all_opps = []
    
    while True:
        cycle += 1
        print(f"\n--- Scan cycle {cycle} @ {time.strftime('%H:%M:%S')} ---")
        
        for name, address in TOKENS.items():
            opps = scan_token(name, address)
            all_opps.extend(opps)
            time.sleep(0.5)  # Rate limit
        
        if not all_opps:
            print("   No arbitrage opportunities found this cycle.")
        else:
            print(f"\n📊 Total opportunities found: {len(all_opps)}")
            # Save to file
            with open("arb_opportunities.json", "w") as f:
                json.dump(all_opps, f, indent=2)
        
        all_opps = []
        print(f"\nSleeping 30s before next scan...")
        time.sleep(30)

if __name__ == "__main__":
    main()
