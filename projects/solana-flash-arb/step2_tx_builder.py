#!/usr/bin/env python3
"""
Step 2: Transaction builder for flash loan arbitrage on Solana.
Constructs atomic transactions: flash_loan → swap_A → swap_B → repay.

Iteration 1: Build the framework + Raydium AMM swap instruction decoder.
"""

import json
import struct
import base64
import base58
import requests
from dataclasses import dataclass
from typing import Optional

RPC = "https://api.mainnet-beta.solana.com"

# Program IDs
RAYDIUM_AMM_V4 = "675kPX9MHTjS2zt1qfr1NYHuzeLXfQM9H24wFSUt1Mp8"
RAYDIUM_CPMM = "CPMMoo8L3F4NbTegBCKVNunggL7H1ZpdTHKxQB5qKP1C"
ORCA_WHIRLPOOL = "whirLbMiicVdio4qvUfM5KAg6Ct8VwpYzGff3uctyCc"
METEORA_DLMM = "LBUZKhRxPF3XUpBCjp4YzTKgLccjZhTSDM9YuVaPwxo"
MARGINFI_V2 = "MFv2hWf31Z9kbCa1snEPYctwafyhdvnV7FZnsebVacA"
TOKEN_PROGRAM = "TokenkegQfeZyiNwAJbNbGKPFXCWuBvf9Ss623VQ5DA"

# Known token mints
SOL_MINT = "So11111111111111111111111111111111111111112"
USDC_MINT = "EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v"
RAY_MINT = "4k3Dyjzvzp8eMZWUXbBCjEvwSkkk59S5iCNLY3QrkX6R"


@dataclass
class ArbOpportunity:
    """Represents a detected arbitrage opportunity"""
    token_symbol: str
    token_mint: str
    buy_dex: str
    buy_pool: str
    buy_price: float
    sell_dex: str
    sell_pool: str
    sell_price: float
    spread_pct: float
    net_profit_pct: float
    amount_in_lamports: int  # How much to trade


@dataclass  
class SwapInstruction:
    """A single swap instruction to include in the transaction"""
    program_id: str
    accounts: list  # List of (pubkey, is_signer, is_writable)
    data: bytes


def rpc_call(method, params):
    """Make an RPC call to Solana"""
    resp = requests.post(RPC, json={
        "jsonrpc": "2.0",
        "id": 1, 
        "method": method,
        "params": params
    }, timeout=10)
    return resp.json().get("result")


def get_raydium_pool_info(pool_address: str) -> Optional[dict]:
    """Fetch Raydium AMM pool account data to extract keys needed for swap"""
    result = rpc_call("getAccountInfo", [pool_address, {"encoding": "base64"}])
    if not result or not result.get("value"):
        return None
    
    data_b64 = result["value"]["data"][0]
    data = base64.b64decode(data_b64)
    owner = result["value"]["owner"]
    
    # Raydium AMM v4 pool layout (simplified)
    # The pool account contains all the keys we need for a swap
    if owner == RAYDIUM_AMM_V4 and len(data) >= 752:
        # Parse key fields from the pool state
        # This is the AmmInfo struct layout
        return {
            "program": RAYDIUM_AMM_V4,
            "pool": pool_address,
            "raw_data": data,
            "data_len": len(data),
            "owner": owner,
        }
    
    return {"program": owner, "pool": pool_address, "data_len": len(data)}


def build_raydium_swap_instruction(
    pool_address: str,
    user_wallet: str,
    amount_in: int,
    minimum_out: int,
    is_buy: bool = True,  # True = buy token with SOL, False = sell token for SOL
) -> Optional[SwapInstruction]:
    """
    Build a Raydium AMM v4 swap instruction.
    
    Iteration 1: Get pool info and construct the instruction data.
    This will need refinement based on actual pool account layout.
    """
    pool_info = get_raydium_pool_info(pool_address)
    if not pool_info:
        print(f"  ❌ Could not fetch pool info for {pool_address}")
        return None
    
    print(f"  Pool: {pool_address[:20]}...")
    print(f"  Program: {pool_info['program']}")
    print(f"  Data size: {pool_info['data_len']} bytes")
    
    # Raydium AMM v4 swap instruction discriminator
    # SwapBaseIn = 9 (swap exact amount in)
    # The instruction data is: [discriminator(1), amount_in(8), minimum_out(8)]
    ix_data = struct.pack("<BQQ", 9, amount_in, minimum_out)
    
    # For a full swap, we need these accounts (in order):
    # 0. Token program
    # 1. AMM id (pool)
    # 2. AMM authority  
    # 3. AMM open orders
    # 4. AMM target orders (can be same as pool for CPMM)
    # 5. Pool coin token account
    # 6. Pool pc token account
    # 7. Serum program id
    # 8. Serum market
    # 9. Serum bids
    # 10. Serum asks
    # 11. Serum event queue
    # 12. Serum coin vault
    # 13. Serum pc vault
    # 14. Serum vault signer
    # 15. User source token account
    # 16. User destination token account
    # 17. User wallet (signer)
    
    # TODO: Parse these from the pool account data
    # This is where iteration 2 comes in - we need to decode the pool state
    
    return SwapInstruction(
        program_id=pool_info['program'],
        accounts=[],  # TODO: fill in iteration 2
        data=ix_data,
    )


def estimate_profit(opp: ArbOpportunity) -> dict:
    """Estimate real profit after all costs"""
    trade_amount_usd = 1000  # Flash loan $1000 worth
    
    # Buy
    tokens_bought = trade_amount_usd / opp.buy_price
    buy_fee = trade_amount_usd * 0.003  # 0.3% DEX fee
    
    # Sell
    sell_revenue = tokens_bought * opp.sell_price
    sell_fee = sell_revenue * 0.003
    
    # Flash loan fee (Marginfi: 0 fee for flash loans!)
    flash_fee = 0
    
    # Gas
    gas_sol = 0.001  # ~0.001 SOL
    gas_usd = gas_sol * 89.57
    
    # Jito tip (optional, for priority)
    jito_tip_sol = 0.0001
    jito_tip_usd = jito_tip_sol * 89.57
    
    gross_profit = sell_revenue - trade_amount_usd - buy_fee - sell_fee
    net_profit = gross_profit - flash_fee - gas_usd - jito_tip_usd
    
    return {
        "trade_amount": trade_amount_usd,
        "tokens_bought": tokens_bought,
        "sell_revenue": sell_revenue,
        "gross_profit": gross_profit,
        "fees": buy_fee + sell_fee,
        "gas": gas_usd,
        "jito_tip": jito_tip_usd,
        "net_profit": net_profit,
        "profitable": net_profit > 0,
    }


def test_pool_fetch():
    """Test fetching real Raydium pool data"""
    # RAY/USDC Raydium pool (one of the most liquid)
    ray_usdc_pool = "6UmmUiYoBjSrhakAobJw8BvU6pWH6R5Mgg8rU7FTHeCN"
    
    print("=== Testing Raydium Pool Fetch ===")
    info = get_raydium_pool_info(ray_usdc_pool)
    if info:
        print(f"  ✅ Pool fetched successfully")
        print(f"  Program: {info['program']}")
        print(f"  Data length: {info['data_len']} bytes")
        
        if info.get('raw_data'):
            data = info['raw_data']
            # Try to decode some known fields
            # First 8 bytes = status/nonce
            print(f"  First 16 bytes: {data[:16].hex()}")
    else:
        print("  ❌ Failed to fetch pool")


def main():
    print("=" * 60)
    print("  STEP 2: Transaction Builder — Iteration 1")
    print("=" * 60)
    
    # Test pool data fetch
    test_pool_fetch()
    
    print()
    
    # Create a sample opportunity from our scanner results
    opp = ArbOpportunity(
        token_symbol="RAY",
        token_mint=RAY_MINT,
        buy_dex="raydium",
        buy_pool="6UmmUiYoBjSrhakAobJw8BvU6pWH6R5Mgg8rU7FTHeCN",
        buy_price=0.6428,
        sell_dex="raydium",
        sell_pool="",  # Different pool
        sell_price=0.6757,
        spread_pct=5.12,
        net_profit_pct=4.52,
        amount_in_lamports=1_000_000_000,  # 1 SOL worth
    )
    
    # Estimate profit
    print("=== Profit Estimation ===")
    est = estimate_profit(opp)
    for k, v in est.items():
        if isinstance(v, float):
            print(f"  {k}: ${v:.4f}")
        else:
            print(f"  {k}: {v}")
    
    print()
    
    # Try building a swap instruction
    print("=== Building Swap Instruction ===")
    ix = build_raydium_swap_instruction(
        pool_address=opp.buy_pool,
        user_wallet="EXEDJvuAaYt9yN5mwZRPdCP19tYuF6LWztnu6qpbepTq",
        amount_in=opp.amount_in_lamports,
        minimum_out=0,  # TODO: calculate from price
    )
    
    if ix:
        print(f"  ✅ Instruction built")
        print(f"  Data: {ix.data.hex()}")
    
    print()
    print("=== Next Iteration Needed ===")
    print("  1. Decode Raydium pool state to extract all account keys")
    print("  2. Build the full account list for swap instruction")
    print("  3. Add Marginfi flash loan borrow/repay instructions")
    print("  4. Compose full atomic transaction")
    print("  5. Test with simulated tx (simulateTransaction RPC)")


if __name__ == "__main__":
    main()
