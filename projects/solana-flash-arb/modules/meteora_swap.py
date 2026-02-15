"""
Meteora DLMM Swap — Reverse-engineered from on-chain transactions
Discriminator: f8c69e91e17587c8

Decoded from tx: 4iH4PBp33ZcrPuWu9EYFHwUZfgNRQdP2DocjoccqUM7z
Pool: 6oFWm7KPLfxnwMb3z5xwBoXNSPP3JJyirAPqPSiVcnsp (BONK/SOL)
"""

import struct
from dataclasses import dataclass

METEORA_DLMM_PROGRAM = "LBUZKhRxPF3XUpBCjp4YzTKgLccjZhTSDM9YuVaPwxo"
SWAP_DISCRIMINATOR = bytes.fromhex("f8c69e91e17587c8")

@dataclass
class MeteoraPool:
    """Decoded from on-chain account data (904 bytes)"""
    address: str           # Pool PDA
    mint_x: str           # Token A mint
    mint_y: str           # Token B mint  
    reserve_x: str        # Token A vault
    reserve_y: str        # Token B vault
    oracle: str           # Oracle account
    active_id: int        # Current active bin
    bin_step: int         # Bin width in bps
    
# Pool 1: BONK/SOL high-price pool ($0.000007143)
POOL_HIGH = MeteoraPool(
    address="6Qmm15WNFfA5MhAxknsQjmxX2kGqb8H3qCoZwfWVxRNB",
    mint_x="DezXAZ8z7PnrnRJjz3wXBoRgixCa6xjnB7YaB1pPB263",  # BONK
    mint_y="So11111111111111111111111111111111111111112",        # wSOL
    reserve_x="13grxnxkeiyVBycg6R2w8RqXxM16rLnA8awuMFf6YMPH",
    reserve_y="8o3V6AYjnPRoZkPKLYmxPXv2EgZ5bfC8M5UyzJcso3Yj",
    oracle="H4aPFEMHmPUWCizkdbryj182TzXpiMs76SroK7xMdEVM",
    active_id=-182,
    bin_step=400,
)

# Pool 2: BONK/SOL low-price pool ($0.000006923, $227K liq, 2523 SOL)
POOL_LOW = MeteoraPool(
    address="6oFWm7KPLfxnwMb3z5xwBoXNSPP3JJyirAPqPSiVcnsp",
    mint_x="DezXAZ8z7PnrnRJjz3wXBoRgixCa6xjnB7YaB1pPB263",  # BONK
    mint_y="So11111111111111111111111111111111111111112",        # wSOL
    reserve_x="D4uJ9ASY1y1qsQ8g4vgv7V514VVsBK5sdAVJkSYqLYPj",
    reserve_y="CDxKWsQbe2HWLzvUZ7hAPvhk7381WjFGYMXYVG8Ahdim",
    oracle="",  # TBD
    active_id=-8968,
    bin_step=8,
)

def build_swap_data(amount_in: int, min_amount_out: int) -> bytes:
    """
    Build Meteora DLMM swap instruction data.
    Layout: disc(8) + amount_in(u64) + min_out(u64) + ... route data
    
    NOTE: The full data is 163 bytes in real txs. The first 24 bytes are
    disc + amount_in + min_out. The remaining ~139 bytes encode the 
    route through bins. For a simple swap, we may need to extract the
    bin traversal data from recent transactions.
    """
    # Basic swap data (first 24 bytes)
    return SWAP_DISCRIMINATOR + struct.pack('<QQ', amount_in, min_amount_out)

def calculate_price(active_id: int, bin_step: int, decimal_diff: int = -4) -> float:
    """
    Calculate DLMM price from active_id and bin_step.
    price = (1 + bin_step/10000) ^ active_id * 10^decimal_diff
    decimal_diff = decimals_x - decimals_y (BONK=5, SOL=9 → -4)
    """
    return (1 + bin_step / 10000) ** active_id * 10 ** decimal_diff

if __name__ == "__main__":
    print("=== Meteora DLMM Pools ===")
    for name, pool in [("HIGH", POOL_HIGH), ("LOW", POOL_LOW)]:
        price = calculate_price(pool.active_id, pool.bin_step)
        print(f"\n{name} Pool: {pool.address}")
        print(f"  active_id={pool.active_id}, bin_step={pool.bin_step}")
        print(f"  Price: {price:.12f} SOL/BONK")
        print(f"  Price: ${price * 90.13:.10f} USD/BONK")
    
    spread = (POOL_HIGH.active_id - POOL_LOW.active_id)
    p_high = calculate_price(POOL_HIGH.active_id, POOL_HIGH.bin_step) * 90.13
    p_low = calculate_price(POOL_LOW.active_id, POOL_LOW.bin_step) * 90.13
    print(f"\nSpread: ${p_high:.10f} vs ${p_low:.10f} = {(p_high/p_low - 1)*100:.2f}%")
    print(f"Swap disc: {SWAP_DISCRIMINATOR.hex()}")
