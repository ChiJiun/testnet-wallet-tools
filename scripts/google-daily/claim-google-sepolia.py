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
                return
        print("Submitting one Ethereum Sepolia claim", flush=True)
        call(base + f"/element/{element}/click", {})
        for _ in range(45):
            page = check_page()
            for link in page["links"]:
                match = HASH.search(link)
                if match:
                    print("Claim transaction:", match.group(), flush=True)
                    return
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


if __name__ == "__main__":
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
            sys.exit(0)
        index = today.toordinal() % len(addresses)
        print(f"Google Faucet recipient index: {index}", flush=True)
        sys.argv[1] = addresses[index]
    if len(sys.argv) != 2 or not ADDRESS.fullmatch(sys.argv[1]):
        sys.exit("Supply one public Ethereum address")
    try:
        run(sys.argv[1], marker)
    except RuntimeError as error:
        sys.exit(str(error))
    except Exception as error:
        sys.exit(f"Browser automation failed ({type(error).__name__})")
