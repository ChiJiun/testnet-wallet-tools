#!/usr/bin/env python3
"""Testnet HD-wallet inventory and opt-in native-token transfers."""
import argparse
import json
import os
import sys
from decimal import Decimal
from pathlib import Path

import requests
from eth_account import Account
from mnemonic import Mnemonic

ROOT = Path(__file__).resolve().parent
Account.enable_unaudited_hdwallet_features()
TIMEOUT = 15


def wallets(count):
    path = ROOT / "secrets" / "mnemonic.txt"
    if path.is_symlink():
        raise ValueError("Refusing symlink mnemonic")
    phrase = path.read_text(encoding="utf-8").strip()
    if not Mnemonic("english").check(phrase):
        raise ValueError("Invalid BIP39 mnemonic")
    return [Account.from_mnemonic(phrase, account_path=f"m/44'/60'/0'/0/{i}") for i in range(count)]


def rpc(url, method, params=None):
    if not url.startswith(("https://", "http://127.0.0.1:", "http://localhost:")):
        raise ValueError("RPC URL must use HTTPS (or local loopback)")
    response = requests.post(url, json={"jsonrpc": "2.0", "id": 1, "method": method, "params": params or []}, timeout=TIMEOUT)
    response.raise_for_status()
    data = response.json()
    if "error" in data:
        raise RuntimeError(f"RPC {method}: {data['error'].get('message', 'unknown error')}")
    if "result" not in data:
        raise RuntimeError(f"RPC {method}: missing result")
    return data["result"]


def network(name):
    config = json.loads((ROOT / "networks.json").read_text(encoding="utf-8"))
    if name not in config:
        raise ValueError("Unknown network: " + name)
    item = config[name]
    url = os.environ.get(item["rpc_env"])
    if not url:
        raise ValueError(f"Set {item['rpc_env']} to a trusted RPC HTTPS endpoint")
    actual = int(rpc(url, "eth_chainId"), 16)
    if item["chain_id"] is None:
        raise ValueError(f"Configure the verified chain_id for {name} in networks.json (RPC reports {actual})")
    if actual != item["chain_id"]:
        raise ValueError(f"Chain ID mismatch: configured {item['chain_id']}, RPC returned {actual}")
    return url, actual


def balance(url, address):
    return int(rpc(url, "eth_getBalance", [address, "latest"]), 16)


def fee_fields(url):
    try:
        block = rpc(url, "eth_getBlockByNumber", ["latest", False])
        if block.get("baseFeePerGas") is not None:
            priority = int(rpc(url, "eth_maxPriorityFeePerGas"), 16)
            base = int(block["baseFeePerGas"], 16)
            return {"maxPriorityFeePerGas": priority, "maxFeePerGas": 2 * base + priority}
    except (RuntimeError, ValueError, KeyError):
        pass
    return {"gasPrice": int(rpc(url, "eth_gasPrice"), 16)}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=["addresses", "networks", "balances", "sweep"])
    parser.add_argument("--network", help="Network key in networks.json")
    parser.add_argument("--count", type=int, default=5)
    parser.add_argument("--execute", action="store_true", help="Broadcast transfers (default: dry-run)")
    parser.add_argument("--confirm", help="Must be exactly TRANSFER-TESTNET-FUNDS")
    parser.add_argument("--reserve-wei", type=int, default=0, help="Extra amount to leave on each source")
    args = parser.parse_args()
    if not 1 <= args.count <= 100:
        parser.error("--count must be 1..100")
    if args.reserve_wei < 0:
        parser.error("--reserve-wei must be nonnegative")
    if args.command == "networks":
        for name, item in json.loads((ROOT / "networks.json").read_text()).items():
            print(name, "chain_id=", item["chain_id"], "rpc_env=", item["rpc_env"], "faucet_info=", item["faucet"])
        return
    accounts = wallets(args.count)
    if args.command == "addresses":
        for i, acct in enumerate(accounts):
            print(i, acct.address)
        return
    if not args.network:
        parser.error("--network is required for balances/sweep")
    url, chain_id = network(args.network)
    if args.command == "balances":
        for i, acct in enumerate(accounts):
            amount = balance(url, acct.address)
            print(i, acct.address, f"{Decimal(amount) / Decimal(10**18):f}", "native units")
        return
    if args.execute and args.confirm != "TRANSFER-TESTNET-FUNDS":
        parser.error("--execute requires --confirm TRANSFER-TESTNET-FUNDS")
    if args.count < 2:
        parser.error("sweep requires at least 2 addresses")
    destination = accounts[0].address
    print("NETWORK:", args.network, "CHAIN ID:", chain_id, "DESTINATION:", destination)
    for i, acct in enumerate(accounts[1:], start=1):
        amount = balance(url, acct.address)
        fields = fee_fields(url)
        fee_per_gas = fields.get("maxFeePerGas", fields.get("gasPrice"))
        gas_limit = 21000
        cost = gas_limit * fee_per_gas
        value = amount - cost - args.reserve_wei
        if value <= 0:
            print(i, "SKIP insufficient funds after fee/reserve")
            continue
        tx = {"chainId": chain_id, "to": destination, "value": value, "nonce": int(rpc(url, "eth_getTransactionCount", [acct.address, "pending"]), 16), "gas": gas_limit, **fields}
        print(i, acct.address, "->", destination, "value_wei=", value, "max_fee_wei=", cost, "mode=", "BROADCAST" if args.execute else "DRY-RUN")
        if args.execute:
            signed = acct.sign_transaction(tx)
            tx_hash = rpc(url, "eth_sendRawTransaction", ["0x" + signed.raw_transaction.hex()])
            print("  tx_hash:", tx_hash)
    if not args.execute:
        print("No transactions broadcast. To execute, pass --execute --confirm TRANSFER-TESTNET-FUNDS")


if __name__ == "__main__":
    try:
        main()
    except (OSError, ValueError, RuntimeError, requests.RequestException) as exc:
        print("ERROR:", exc, file=sys.stderr)
        sys.exit(1)
