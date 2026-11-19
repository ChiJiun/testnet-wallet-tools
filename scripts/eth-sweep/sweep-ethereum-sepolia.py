import os
import sys
import time
from datetime import datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

sys.path.insert(0, "/home/devspace/projects/testnet-wallet-tools")
from wallet import balance, fee_fields, rpc, wallets

NETWORK = 11155111
URL = "https://ethereum-sepolia-rpc.publicnode.com"
GAS = 21000


def sweep(account, target):
    amount = balance(URL, account.address)
    if not amount:
        return None
    fees = fee_fields(URL)
    maximum_fee = GAS * (fees.get("maxFeePerGas") or fees["gasPrice"])
    if amount <= maximum_fee:
        return None
    nonce = int(rpc(URL, "eth_getTransactionCount", [account.address, "pending"]), 16)
    signed = account.sign_transaction(dict(
        chainId=NETWORK, to=target, value=amount - maximum_fee,
        gas=GAS, nonce=nonce, **fees
    ))
    tx = rpc(URL, "eth_sendRawTransaction", ["0x" + signed.raw_transaction.hex()])
    deadline = time.monotonic() + 80
    while time.monotonic() < deadline:
        receipt = rpc(URL, "eth_getTransactionReceipt", [tx])
        if receipt is not None:
            if int(receipt["status"], 16) != 1:
                raise RuntimeError("Sweep reverted")
            return tx
        time.sleep(4)
    raise TimeoutError("Sweep receipt timed out")


def main():
    indices = set(range(1, 10))
    today = datetime.now(ZoneInfo("Asia/Taipei")).date()
    for day in (today, today - timedelta(days=1)):
        record = Path("/var/lib/google-sepolia-claim") / (day.isoformat() + ".indices")
        if record.is_file():
            indices.update(int(i) for i in record.read_text().splitlines() if i.isdecimal() and 0 < int(i) < 1000)
    accounts = wallets(max(indices) + 1)
    target = accounts[0].address
    if target.lower() != os.environ.get("CELO_FAUCET_BENEFICIARY", "").lower():
        raise ValueError("Configured beneficiary does not match index 0")
    if int(rpc(URL, "eth_chainId"), 16) != NETWORK:
        raise ValueError("RPC is not Ethereum Sepolia")
    if rpc(URL, "eth_getCode", [target, "latest"]) != "0x":
        raise ValueError("Expected a regular collector account")
    failed = False
    for i in sorted(indices):
        account = accounts[i]
        try:
            tx = sweep(account, target)
            print(f"Index {i}: confirmed {tx}" if tx else f"Index {i}: no ETH above gas cost")
        except Exception as error:
            failed = True
            print(f"Index {i}: sweep failed ({type(error).__name__})", file=sys.stderr)
    return int(failed)


try:
    sys.exit(main())
except Exception as error:
    sys.exit(f"Sweep failed ({type(error).__name__})")
