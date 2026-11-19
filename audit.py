#!/usr/bin/env python3
"""Read-only testnet holdings and transaction receipt audit."""
import argparse
import json
import os
from datetime import datetime, timezone
from pathlib import Path

from wallet import wallets, network, balance, rpc
from tokens import token_balance, token_decimals, valid_address

ROOT = Path(__file__).resolve().parent


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--network", action="append", help="Network name; repeat for multiple networks")
    p.add_argument("--count", type=int, default=5)
    p.add_argument("--token", action="append", default=[], help="Verified ERC20 address; repeat for more")
    p.add_argument("--tx", action="append", default=[], help="Transaction hash to verify receipt; repeat for more")
    p.add_argument("--output", help="Optional JSON report path (must not be under secrets/)")
    args = p.parse_args()
    if not 1 <= args.count <= 100:
        p.error("--count must be 1..100")
    networks = json.loads((ROOT / "networks.json").read_text())
    selected = args.network or [name for name, c in networks.items() if os.environ.get(c["rpc_env"])]
    if not selected:
        p.error("No RPC configured. Set RPC_* environment variables or pass --network to see a configuration error")
    accounts = wallets(args.count)
    report = {"checked_at": datetime.now(timezone.utc).isoformat(), "networks": {}, "warning": "A positive balance alone does not prove a faucet claim. Confirm tx receipt and sender with provider."}
    for name in selected:
        try:
            url, chain_id = network(name)
            records = []
            for i, acct in enumerate(accounts):
                item = {"index": i, "address": acct.address, "native_wei": str(balance(url, acct.address)), "tokens": {}}
                for token in args.token:
                    contract = valid_address(token)
                    item["tokens"][contract] = {"units": str(token_balance(url, contract, acct.address)), "decimals": token_decimals(url, contract)}
                records.append(item)
            receipts = {}
            for tx in args.tx:
                if len(tx) != 66 or not tx.startswith("0x") or any(ch not in "0123456789abcdefABCDEF" for ch in tx[2:]):
                    raise ValueError("Invalid transaction hash")
                receipt = rpc(url, "eth_getTransactionReceipt", [tx])
                receipts[tx] = {"status": "not mined" if receipt is None else ("success" if int(receipt["status"], 16) == 1 else "reverted"), "block": None if receipt is None else receipt["blockNumber"], "to": None if receipt is None else receipt.get("to")}
            report["networks"][name] = {"chain_id": chain_id, "accounts": records, "receipts": receipts}
        except (ValueError, RuntimeError, OSError, KeyError) as exc:
            report["networks"][name] = {"error": str(exc)}
    result = json.dumps(report, indent=2)
    if args.output:
        dest = Path(args.output).resolve()
        if dest.is_relative_to((ROOT / "secrets").resolve()):
            p.error("Refusing report output under secrets/")
        dest.parent.mkdir(parents=True, exist_ok=True)
        fd = os.open(dest, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
        with os.fdopen(fd, "w") as f:
            f.write(result + "\n")
        print("Report written:", dest)
    else:
        print(result)


if __name__ == "__main__":
    main()
