#!/usr/bin/env python3
"""Solana Cross-DEX Arb Bot - Meteora DLMM <> Raydium CLMM
Monitors BONK/SOL price spread and executes atomic arb when profitable.
Built by 13 AIs with $0.47 of capital.
"""
import json, struct, urllib.request, base64, time, sys
from solders.pubkey import Pubkey
from solders.keypair import Keypair
from solders.instruction import Instruction, AccountMeta
from solders.transaction import Transaction
from solders.message import Message
from solders.hash import Hash
from solders.compute_budget import set_compute_unit_limit, set_compute_unit_price
from solders.system_program import transfer, TransferParams

URL = "https://api.mainnet-beta.solana.com"
WALLET_PATH = "data/wallet/solana-wallet.json"

# Programs
METEORA = Pubkey.from_string("LBUZKhRxPF3XUpBCjp4YzTKgLccjZhTSDM9YuVaPwxo")
RAYDIUM = Pubkey.from_string("CAMMCzo5YL8w4VFF8KVHrK22GGUsp5VTaW7grrKgrWqK")
SPL = Pubkey.from_string("TokenkegQfeZyiNwAJbNbGKPFXCWuBvf9Ss623VQ5DA")
ASSOC = Pubkey.from_string("ATokenGPvbdGVxr1b2hvZbsiqW5xWH25efTNsLJA8knL")
SYS = Pubkey.from_string("11111111111111111111111111111111")
BONK = Pubkey.from_string("DezXAZ8z7PnrnRJjz3wXBoRgixCa6xjnB7YaB1pPB263")
WSOL = Pubkey.from_string("So11111111111111111111111111111111111111112")

# Meteora Pool LOW accounts
M_POOL = Pubkey.from_string("6oFWm7KPLfxnwMb3z5xwBoXNSPP3JJyirAPqPSiVcnsp")
M_RES_X = Pubkey.from_string("D4uJ9ASY1y1qsQ8g4vgv7V514VVsBK5sdAVJkSYqLYPj")
M_RES_Y = Pubkey.from_string("CDxKWsQbe2HWLzvUZ7hAPvhk7381WjFGYMXYVG8Ahdim")
M_ORACLE = Pubkey.from_string("4VcvJar1yrCSCgXGj9r2c1VvmA22Ag561Dp6WYrDALms")
M_EVT = Pubkey.from_string("D1ZN9Wj1fRSUQfCjhvnu1hqDMT7hzjzBBpi12nVniYD6")
M_BIN = [Pubkey.from_string(x) for x in [
    "ENxyuWxbwyJ5T7km2HXCMsuwqDKARSq2DWZy7RevNddJ",
    "A5Xf77uWzRYtgFG7cD3kfaAR5oKrKVj6syGDts5yujfa",
    "9aae8kwAyGStwaCVJkC9YoMWK6qpdQT9cwqbisvxJEAp"]]

# Raydium CLMM accounts
R_POOL = Pubkey.from_string("GtKKKs3yaPdHbQd2aZS4SfWhy8zQ988BJGnKNndLxYsN")
R_CFG = Pubkey.from_string("E64NGkDLLCdQ2yFNPcavaKptrEgmiQaNykUuLC1Qgwyp")
R_V_SOL = Pubkey.from_string("GDnBvA76ZAJ2K3en2F1iExPZ6qz83Xjj5srXMmSKTYDW")
R_V_BONK = Pubkey.from_string("2wzaFLYb4JcDrVs8TfU3TfkVwq1Pdp3rRgWdNJzFGXud")
R_OBS = Pubkey.from_string("Gj8gzDNKmf5y3p1LorKHTvMZ8eCLhbCDnhGiN5xVW8Jq")
R_BMP = Pubkey.from_string("H162txn8gSuXiVfXffF8XxTAoP9KUDrhtktpeDpYEqk4")
R_TICK = [Pubkey.from_string(x) for x in [
    "H8u5Ydtp6bgPXzpdvpdbNjDdffE9csrJfNjgtprMaog6",
    "FohQpHgvyJQHbYvrkyVXGuZpA2aaBXVBeHtEoxe5gzir",
    "CiigF62vU9rt9jf4YRvEWsoZxd3SCxVLXM13SC5C6832"]]

# ATAs
WSOL_ATA = Pubkey.from_string("A4pQpNfLAXt18phQvGee2JTThWtkAz6oRWMU6n3HA82A")
BONK_ATA = Pubkey.from_string("HSc8Ui9JdFJVZHRBUWSfDsdLgxYLG2rwnGiG8baa97US")

DISC = bytes.fromhex("f8c69e91e17587c8")
MIN_SPREAD = 0.003  # 0.3% minimum spread to execute

def rpc(method, params):
    payload = json.dumps({"jsonrpc": "2.0", "id": 1, "method": method, "params": params})
    req = urllib.request.Request(URL, data=payload.encode(), headers={"Content-Type": "application/json"})
    return json.loads(urllib.request.urlopen(req, timeout=10).read())["result"]

def get_meteora_price():
    resp = rpc("getAccountInfo", [str(M_POOL), {"encoding": "base64", "dataSlice": {"offset": 76, "length": 6}}])
    data = base64.b64decode(resp["value"]["data"][0])
    aid = struct.unpack("<i", data[0:4])[0]
    bs = struct.unpack("<H", data[4:6])[0]
    return (1 + bs/10000) ** aid * 1e-4

def get_dexscreener_prices():
    req = urllib.request.Request(
        "https://api.dexscreener.com/latest/dex/tokens/DezXAZ8z7PnrnRJjz3wXBoRgixCa6xjnB7YaB1pPB263",
        headers={"User-Agent": "Mozilla/5.0"})
    resp = json.loads(urllib.request.urlopen(req, timeout=15).read())
    prices = {}
    for p in resp.get("pairs", []):
        if "6oFWm7" in p["pairAddress"]:
            prices["meteora"] = float(p["priceUsd"])
        elif "GtKKKs" in p["pairAddress"]:
            prices["raydium"] = float(p["priceUsd"])
    return prices

def monitor():
    print("=== BONK Cross-DEX Arb Monitor ===")
    print(f"Meteora Pool LOW <> Raydium CLMM")
    print(f"Min spread: {MIN_SPREAD*100:.1f}%")
    print()
    
    while True:
        try:
            prices = get_dexscreener_prices()
            m = prices.get("meteora", 0)
            r = prices.get("raydium", 0)
            if m and r:
                spread = (m - r) / r
                direction = "Buy Ray→Sell Met" if spread > 0 else "Buy Met→Sell Ray"
                profitable = abs(spread) > MIN_SPREAD
                marker = " 🎯 EXECUTE!" if profitable else ""
                print(f"[{time.strftime('%H:%M:%S')}] Met=${m:.10f} Ray=${r:.10f} spread={spread*100:+.3f}% {direction}{marker}")
                
                if profitable:
                    print(f"  >>> PROFITABLE SPREAD DETECTED: {abs(spread)*100:.3f}% <<<")
                    # TODO: execute arb
            time.sleep(30)
        except KeyboardInterrupt:
            print("\nStopped.")
            break
        except Exception as e:
            print(f"Error: {e}")
            time.sleep(10)

if __name__ == "__main__":
    monitor()
