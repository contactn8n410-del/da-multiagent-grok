"""
Raydium AMM v4 Swap Instruction Builder
Built by FORGE — no SDK, pure on-chain reverse engineering
"""

import struct
from dataclasses import dataclass
from typing import Optional
import json
import httpx

RAYDIUM_AMM_V4 = "675kPX9MHTjS2zt1qfr1NYHuzeLXfQM9H24wFSUt1Mp8"
TOKEN_PROGRAM = "TokenkegQfeZyiNwAJbNbGKPFXCWuBvf9Ss623VQ5DA"
TOKEN_2022 = "TokenzQdBNbLqP5VEhdkAS6EPFLC1PHnBqCXEpPxuEb"

@dataclass
class RaydiumPool:
    amm_id: str
    amm_authority: str
    amm_open_orders: str
    amm_target_orders: str
    pool_coin_token: str
    pool_pc_token: str
    serum_program: str
    serum_market: str
    serum_bids: str
    serum_asks: str
    serum_event_queue: str
    serum_coin_vault: str
    serum_pc_vault: str
    serum_vault_signer: str
    coin_mint: str
    pc_mint: str
    fee_numerator: int = 25
    fee_denominator: int = 10000

def build_swap_data(amount_in: int, min_amount_out: int) -> bytes:
    """Build swap instruction data: discriminator 0x09 + amountIn(u64) + minAmountOut(u64)"""
    return struct.pack('<BQQ', 0x09, amount_in, min_amount_out)

def build_swap_accounts(pool: RaydiumPool, user_source: str, user_dest: str, owner: str) -> list:
    """Build the 18 accounts required for Raydium AMM v4 swap"""
    return [
        {"pubkey": TOKEN_PROGRAM, "is_signer": False, "is_writable": False},
        {"pubkey": pool.amm_id, "is_signer": False, "is_writable": True},
        {"pubkey": pool.amm_authority, "is_signer": False, "is_writable": False},
        {"pubkey": pool.amm_open_orders, "is_signer": False, "is_writable": True},
        {"pubkey": pool.amm_target_orders, "is_signer": False, "is_writable": True},
        {"pubkey": pool.pool_coin_token, "is_signer": False, "is_writable": True},
        {"pubkey": pool.pool_pc_token, "is_signer": False, "is_writable": True},
        {"pubkey": pool.serum_program, "is_signer": False, "is_writable": False},
        {"pubkey": pool.serum_market, "is_signer": False, "is_writable": True},
        {"pubkey": pool.serum_bids, "is_signer": False, "is_writable": True},
        {"pubkey": pool.serum_asks, "is_signer": False, "is_writable": True},
        {"pubkey": pool.serum_event_queue, "is_signer": False, "is_writable": True},
        {"pubkey": pool.serum_coin_vault, "is_signer": False, "is_writable": True},
        {"pubkey": pool.serum_pc_vault, "is_signer": False, "is_writable": True},
        {"pubkey": pool.serum_vault_signer, "is_signer": False, "is_writable": False},
        {"pubkey": user_source, "is_signer": False, "is_writable": True},
        {"pubkey": user_dest, "is_signer": False, "is_writable": True},
        {"pubkey": owner, "is_signer": True, "is_writable": False},
    ]

async def fetch_pool_keys(amm_id: str, rpc_url: str = "https://api.mainnet-beta.solana.com") -> Optional[RaydiumPool]:
    """Fetch pool keys from on-chain account data"""
    async with httpx.AsyncClient() as client:
        resp = await client.post(rpc_url, json={
            "jsonrpc": "2.0", "id": 1,
            "method": "getAccountInfo",
            "params": [amm_id, {"encoding": "base64"}]
        })
        data = resp.json()
        if not data.get("result", {}).get("value"):
            return None
        # TODO: decode AMM layout (752 bytes) to extract all pubkeys
        # For now, pool keys must be provided manually or from API
        return None

def calculate_swap_output(amount_in: int, reserve_in: int, reserve_out: int, fee_num: int = 25, fee_den: int = 10000) -> int:
    """Constant product AMM: (x + dx)(y - dy) = xy, with fees"""
    amount_with_fee = amount_in * (fee_den - fee_num)
    numerator = amount_with_fee * reserve_out
    denominator = reserve_in * fee_den + amount_with_fee
    return numerator // denominator

if __name__ == "__main__":
    # Test: calculate BONK→SOL swap output
    # Pool: ~1B BONK, ~15000 SOL (example reserves)
    bonk_in = 10_000_000 * 10**5  # 10M BONK (5 decimals)
    reserve_bonk = 1_000_000_000 * 10**5
    reserve_sol = 15_000 * 10**9  # 15K SOL (9 decimals)
    
    sol_out = calculate_swap_output(bonk_in, reserve_bonk, reserve_sol)
    print(f"Swap 10M BONK → {sol_out / 10**9:.6f} SOL")
    print(f"Effective price: ${sol_out / 10**9 * 90.13 / 10_000_000:.10f} per BONK")
    print(f"Market price:    $0.000006930 per BONK")
