#!/usr/bin/env python3
import json
import os
import re
import sys
import time
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import HTTPRedirectHandler, Request, build_opener

BASE = "https://faucet.celo.org"
NETWORK = "celo-sepolia"


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, *args, **kwargs):
        return None


def fetch(path, data=None, key=None):
    headers = {"Accept": "application/json"}
    body = None
    if data is not None:
        headers["Content-Type"] = "application/json"
        body = json.dumps(data).encode()
    if key is not None:
        headers["Authorization"] = f"Bearer {key}"
    try:
        with build_opener(NoRedirect()).open(
            Request(BASE + path, data=body, headers=headers), timeout=12
        ) as response:
            result = json.load(response)
    except HTTPError as error:
        raise ValueError(f"Faucet HTTP {error.code}") from None
    except (URLError, TimeoutError, ValueError):
        raise ValueError("Faucet request failed or returned invalid JSON") from None
    if not isinstance(result, dict):
        raise ValueError("Unexpected faucet response")
    return result


PROJECT = Path(os.environ.get("WALLET_PROJECT", "/home/devspace/projects/testnet-wallet-tools"))
sys.path.insert(0, str(PROJECT))
from wallet import balance, fee_fields, rpc, wallets
from eth_utils import keccak

RPC = "https://forno.celo-sepolia.celo-testnet.org"
CHAIN = 11142220
COUNT = 5


def confirmed(tx):
    deadline = time.monotonic() + 70
    while time.monotonic() < deadline:
        receipt = rpc(RPC, "eth_getTransactionReceipt", [tx])
        if receipt is not None:
            if int(receipt["status"], 16) != 1:
                raise ValueError("Transaction reverted")
            return
        time.sleep(4)
    raise ValueError("On-chain receipt timed out")


def sweep(account, target):
    amount = balance(RPC, account.address)
    fees = fee_fields(RPC)
    gas = 21000
    # Leave a small cushion for Celo L2 data fees in addition to execution gas.
    value = amount - gas * (fees.get("maxFeePerGas") or fees["gasPrice"]) - 10**15
    if value <= 0:
        raise ValueError("Insufficient balance for sweep and fees")
    nonce = int(rpc(RPC, "eth_getTransactionCount", [account.address, "pending"]), 16)
    signed = account.sign_transaction(dict(chainId=CHAIN, to=target, value=value, nonce=nonce, gas=gas, **fees))
    tx = "0x" + keccak(signed.raw_transaction).hex()
    submitted = rpc(RPC, "eth_sendRawTransaction", ["0x" + signed.raw_transaction.hex()])
    if submitted.lower() != tx.lower():
        raise ValueError("RPC returned an unexpected transaction hash")
    confirmed(tx)
    return tx


def main():
    key = os.environ.get("CELO_FAUCET_API_KEY", "")
    if not re.fullmatch(r"[A-Za-z0-9._~+/=-]+", key):
        raise ValueError("Configure CELO_FAUCET_API_KEY")
    accounts = wallets(COUNT)
    target = accounts[0].address
    if target.lower() != os.environ.get("CELO_FAUCET_BENEFICIARY", "").lower():
        raise ValueError("Configured beneficiary must match derived index 0")
    if int(rpc(RPC, "eth_chainId"), 16) != CHAIN:
        raise ValueError("RPC chain ID mismatch")
    if rpc(RPC, "eth_getCode", [target, "latest"]) != "0x":
        raise ValueError("Configured beneficiary must be a regular account")
    if sys.argv[1:] == ["--check-config"]:
        print("Validated 5 derived accounts, beneficiary and Celo Sepolia RPC")
        return

    state = Path(os.environ["STATE_DIRECTORY"])
    pending = {}
    failures = []
    for index, account in enumerate(accounts):
        try:
            result = fetch("/api/faucet", {"beneficiary": account.address, "network": NETWORK}, key)
            request_key = result.get("key")
            if not isinstance(request_key, str) or not request_key:
                raise ValueError("Faucet did not return a request key")
            pending[index] = request_key
        except ValueError as error:
            print(f"Index {index}: {error}", file=sys.stderr)
            failures.append(index)
            if str(error) in ("Faucet HTTP 401", "Faucet HTTP 429"):
                break

    claims = {}
    deadline = time.monotonic() + 140
    while pending and time.monotonic() < deadline:
        for index, request_key in list(pending.items()):
            query = urlencode({"key": request_key, "network": NETWORK})
            try:
                result = fetch("/api/status?" + query)
            except ValueError:
                continue
            tx = result.get("txHash")
            if result.get("status") == "Done" and isinstance(tx, str) and re.fullmatch(r"0x[0-9a-fA-F]{64}", tx):
                claims[index] = tx
                del pending[index]
            elif result.get("status") == "Failed":
                failures.append(index)
                del pending[index]
        if pending:
            time.sleep(6)

    for index, tx in claims.items():
        try:
            confirmed(tx)
            print(f"Index {index} claim confirmed: {tx}")
            if index:
                print(f"Index {index} sweep confirmed: {sweep(accounts[index], target)}")
        except Exception as error:
            # RPC exceptions may contain request data. Log the type only.
            print(f"Index {index} receipt or sweep failed ({type(error).__name__})", file=sys.stderr)
            failures.append(index)
    if failures or len(claims) != COUNT:
        raise ValueError(f"Batch incomplete: {len(claims)}/{COUNT} payout hashes, failed or pending indices {sorted(set(failures) | set(pending))}")
    temporary = state / "last-success.tmp"
    temporary.write_text(claims[0] + "\n")
    temporary.replace(state / "last-success")


if __name__ == "__main__":
    try:
        main()
    except ValueError as error:
        sys.exit(str(error))
    except Exception as error:
        sys.exit(f"Batch failed ({type(error).__name__})")
