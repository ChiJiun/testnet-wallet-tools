import json
import os
import re
import subprocess
import sys
import time
from urllib.error import URLError
from urllib.request import Request, urlopen

PORT = 47493
URL = "https://cloud.google.com/application/web3/faucet/ethereum/sepolia"
PROFILE = "/home/ubuntu/snap/firefox/common/web3-faucet-profile"
ADDRESS = re.compile(r"0x[0-9a-fA-F]{40}")
HASH = re.compile(r"0x[0-9a-fA-F]{64}")
JS = r"""
const input = Array.from(document.querySelectorAll('input')).find(
    x => x.placeholder?.includes('vitalik') || x.getAttribute('aria-label')?.includes('Wallet address')
);
return {input: input || null, text: document.body?.innerText || '', links:
    Array.from(document.querySelectorAll('a[href]')).map(a => a.href).filter(h => /\/tx\/0x/.test(h))};
"""


def call(path, body=None, method=None):
    data = None if body is None else json.dumps(body).encode()
    request = Request(f"http://127.0.0.1:{PORT}{path}", data=data,
                      headers={"Content-Type": "application/json"}, method=method)
    with urlopen(request, timeout=65) as response:
        return json.load(response)["value"]


def run(address, marker=None):
    driver = subprocess.Popen(["/snap/bin/geckodriver", "--host", "127.0.0.1", "--port", str(PORT)],
                              stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    session = None
    try:
        for _ in range(25):
            try:
                call("/status")
                break
            except URLError:
                time.sleep(0.4)
        session = call("/session", {"capabilities": {"alwaysMatch": {
            "browserName": "firefox",
            "moz:firefoxOptions": {"binary": "/snap/firefox/current/usr/lib/firefox/firefox", "args": [
                "-headless", "-no-remote", "-profile", PROFILE
            ]}
        }}})["sessionId"]
        base = "/session/" + session
        call(base + "/url", {"url": URL})
        call(base + "/timeouts", {"implicit": 0, "script": 20000, "pageLoad": 35000})

        def execute(script):
            return call(base + "/execute/sync", {"script": script, "args": []})

        def check_page():
            if not call(base + "/url").startswith(URL):
                if "accounts.google.com/" in call(base + "/url"):
                    raise RuntimeError("FAUCET_AUTH_REQUIRED: Google sign-in required")
                raise RuntimeError("Google navigated away from the faucet")
            return execute(JS)

        for _ in range(20):
            page = check_page()
            if page["input"]:
                break
            time.sleep(1)
        else:
            raise RuntimeError("Could not find the faucet address field")
        if "sign in to" in page["text"].lower():
            raise RuntimeError("FAUCET_AUTH_REQUIRED: Google sign-in required")
        element = next(iter(page["input"].values()))
        call(base + f"/element/{element}/value", {"text": address})
        button = execute("""
            return Array.from(document.querySelectorAll('button')).find(
                b => /Get .*Sepolia ETH/i.test(b.innerText) && !b.disabled
            ) || null;
        """)
        if not button:
            raise RuntimeError("Claim button unavailable")
        element = next(iter(button.values()))
        if marker is not None:
            try:
                marker.touch(mode=0o600, exist_ok=False)
            except FileExistsError:
                print('Google Faucet already attempted today', flush=True)
                return None
        print("Submitting one Ethereum Sepolia claim", flush=True)
        call(base + f"/element/{element}/click", {})
        for _ in range(45):
            page = check_page()
            for link in page["links"]:
                match = HASH.search(link)
                if match:
                    return match.group()
            text = page["text"].lower()
            if any(message in text for message in (
                "rate limit exceeded", "try again tomorrow", "daily limit reached", "too many requests",
                "have already", "quota exceeded", "claim limit", "verify you are human",
            )):
                raise RuntimeError("Faucet reported a quota or verification requirement")
            time.sleep(2)
        raise RuntimeError("No transaction hash returned after submission; check chain before retrying")
    finally:
        if session:
            try:
                call("/session/" + session, method="DELETE")
            except Exception:
                pass
        driver.terminate()
        driver.wait(timeout=10)


def confirm_claim(address, tx):
    request = Request(
        "https://ethereum-sepolia-rpc.publicnode.com",
        data=json.dumps({
            "jsonrpc": "2.0", "id": 1, "method": "eth_getTransactionReceipt", "params": [tx],
        }).encode(),
        headers={"Content-Type": "application/json"},
    )
    for _ in range(10):
        with urlopen(request, timeout=10) as response:
            receipt = json.load(response).get("result")
        if receipt is not None:
            if receipt.get("status") != "0x1" or (receipt.get("to") or "").lower() != address.lower():
                raise RuntimeError("Unexpected on-chain faucet receipt")
            return
        time.sleep(3)
    raise RuntimeError("Faucet transaction is not yet confirmed on-chain")


def main():
    marker = None
    if sys.argv[1:] == ["--daily"]:
        from datetime import datetime
        from pathlib import Path
        from zoneinfo import ZoneInfo

        addresses = Path("/etc/google-sepolia-addresses").read_text().splitlines()
        if len(addresses) != 10 or not all(ADDRESS.fullmatch(a) for a in addresses):
            sys.exit("Expected 10 configured public addresses")
        today = datetime.now(ZoneInfo("Asia/Taipei")).date()
        marker = Path(os.environ["STATE_DIRECTORY"]) / today.isoformat()
        if marker.exists():
            return
        start = today.toordinal() % len(addresses)
        indices = list(range(start, len(addresses))) + list(range(start))
        recipients = [(i, addresses[i]) for i in indices]
    elif len(sys.argv) == 2 and ADDRESS.fullmatch(sys.argv[1]):
        recipients = [(0, sys.argv[1])]
    else:
        sys.exit("Supply one public Ethereum address or --daily")

    confirmed = 0
    for index, address in recipients:
        print(f"Google Faucet recipient index: {index}", flush=True)
        try:
            tx = run(address, marker if confirmed == 0 else None)
            if tx is None:
                return
            confirm_claim(address, tx)
        except Exception as error:
            reason = str(error) if isinstance(error, RuntimeError) else type(error).__name__
            print(f"Google Faucet stopped at index {index}: {reason}", file=sys.stderr, flush=True)
            if confirmed == 0:
                sys.exit(1)
            break
        confirmed += 1
        print(f"Claim transaction: {tx} (index {index}, confirmed)", flush=True)
    print(f"Google Faucet confirmed {confirmed} claim(s)", flush=True)


if __name__ == "__main__":
    main()
