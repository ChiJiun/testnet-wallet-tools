#!/usr/bin/env python3
"""ERC-20 inventory and opt-in sweep of legitimately acquired test tokens."""
import argparse
import json
import re
import sys
from pathlib import Path

from eth_abi import encode
from eth_utils import keccak
from wallet import wallets, network, rpc, balance, fee_fields

SELECTOR_BALANCE = keccak(text="balanceOf(address)")[:4].hex()
SELECTOR_DECIMALS = keccak(text="decimals()")[:4].hex()
SELECTOR_TRANSFER = keccak(text="transfer(address,uint256)")[:4].hex()


def call(url, contract, data):
    return rpc(url, "eth_call", [{"to": contract, "data": data}, "latest"])


def token_balance(url, contract, address):
    return int(call(url, contract, "0x" + SELECTOR_BALANCE + encode(["address"], [address]).hex()), 16)


def token_decimals(url, contract):
    value = int(call(url, contract, "0x" + SELECTOR_DECIMALS), 16)
    if value > 36:
        raise ValueError("Unexpected token decimals")
    return value


def valid_address(value):
    if not re.fullmatch(r"0x[a-fA-F0-9]{40}", value):
        raise ValueError("Invalid contract address")
    return value


def run(args):
    contract = valid_address(args.contract)
    url, chain_id = network(args.network)
    accounts = wallets(args.count)
    decimals = token_decimals(url, contract)
    print("NETWORK:", args.network, "CHAIN:", chain_id, "CONTRACT:", contract, "DECIMALS:", decimals)
    print("DESTINATION:", accounts[0].address)
    if args.command == "sweep" and args.execute and args.confirm != "TRANSFER-TESTNET-TOKENS":
        raise ValueError("--execute requires --confirm TRANSFER-TESTNET-TOKENS")
    results = []
    for i, acct in enumerate(accounts):
        units = token_balance(url, contract, acct.address)
        row = {"index": i, "address": acct.address, "token_units": str(units)}
        if args.command == "sweep" and i and units:
            data = "0x" + SELECTOR_TRANSFER + encode(["address", "uint256"], [accounts[0].address, units]).hex()
            tx = {"chainId": chain_id, "to": contract, "value": 0, "data": data,
                  "nonce": int(rpc(url, "eth_getTransactionCount", [acct.address, "pending"]), 16),
                  **fee_fields(url)}
            tx["gas"] = int(rpc(url, "eth_estimateGas", [{k: v if k in ("to", "data") else hex(v) if isinstance(v, int) else v for k, v in tx.items() if k != "chainId"} | {"from": acct.address}]), 16)
            max_price = tx.get("maxFeePerGas", tx.get("gasPrice"))
            max_cost = tx["gas"] * max_price
            if balance(url, acct.address) < max_cost:
                row["status"] = "insufficient native gas"
            elif args.execute:
                signed = acct.sign_transaction(tx)
                row["tx_hash"] = rpc(url, "eth_sendRawTransaction", ["0x" + signed.raw_transaction.hex()])
                row["status"] = "broadcast (not confirmed)"
            else:
                row["status"] = "dry-run"
                row["max_fee_wei"] = str(max_cost)
        results.append(row)
    print(json.dumps(results, indent=2))
    if args.command == "sweep" and not args.execute:
        print("DRY-RUN: no transactions broadcast")


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("command", choices=["balances", "sweep"])
    p.add_argument("--network", required=True)
    p.add_argument("--contract", required=True, help="Verified ERC-20 contract address for the selected chain")
    p.add_argument("--count", type=int, default=5)
    p.add_argument("--execute", action="store_true")
    p.add_argument("--confirm")
    args = p.parse_args()
    if not 1 <= args.count <= 100:
        p.error("--count must be 1..100")
    try:
        run(args)
    except (ValueError, RuntimeError, OSError) as e:
        print("ERROR:", e, file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
