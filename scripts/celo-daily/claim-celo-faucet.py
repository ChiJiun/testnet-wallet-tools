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


def main():
    address = os.environ.get("CELO_FAUCET_BENEFICIARY", "")
    key = os.environ.get("CELO_FAUCET_API_KEY", "")
    if not re.fullmatch(r"0x[0-9a-fA-F]{40}", address) or int(address, 16) == 0:
        raise ValueError("Configure a nonzero Celo Sepolia beneficiary address")
    if not re.fullmatch(r"[A-Za-z0-9._~+/=-]+", key):
        raise ValueError("Configure CELO_FAUCET_API_KEY")
    if sys.argv[1:] == ["--check-config"]:
        print("Configuration valid")
        return
    queued = fetch("/api/faucet", {"beneficiary": address, "network": NETWORK}, key)
    request_key = queued.get("key")
    if not isinstance(request_key, str) or not request_key:
        raise ValueError("Faucet did not return a request key")
    query = urlencode({"key": request_key, "network": NETWORK})
    deadline = time.monotonic() + 180
    while time.monotonic() < deadline:
        status = fetch("/api/status?" + query)
        if status.get("status") == "Failed":
            raise ValueError("Faucet reported a failed payout")
        tx_hash = status.get("txHash")
        if status.get("status") == "Done" and isinstance(tx_hash, str) and re.fullmatch(
            r"0x[0-9a-fA-F]{64}", tx_hash
        ):
            stamp = Path(os.environ["STATE_DIRECTORY"]) / "last-success"
            pending = stamp.with_suffix(".tmp")
            pending.write_text(tx_hash + "\n")
            pending.replace(stamp)
            print(f"Faucet completed: {tx_hash}")
            return
        time.sleep(8)
    raise ValueError("Faucet payout was not confirmed before timeout")


if __name__ == "__main__":
    try:
        main()
    except (ValueError, OSError) as error:
        sys.exit(str(error))
