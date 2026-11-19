import concurrent.futures
import json
import re
import subprocess
import sys
import time
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

PORT = 47494
SITES = {
    "Circle": "https://faucet.circle.com/",
    "Alchemy": "https://www.alchemy.com/faucets/ethereum-sepolia",
    "Chainlink": "https://faucets.chain.link/",
    "QuickNode": "https://faucet.quicknode.com/",
    "Google Cloud": "https://cloud.google.com/application/web3/faucet/ethereum/sepolia",
    "Superchain": "https://console.optimism.io/faucet",
    "Coinbase CDP": "https://portal.cdp.coinbase.com/",
    "Solana": "https://faucet.solana.com/",
    "Wormhole Directory": "https://wormhole.com/docs/reference/testnet-faucets/",
    "Celo": "https://faucet.celo.org/",
    "Sui": "https://faucet.sui.io/",
}


def probe(item):
    name, url = item
    try:
        request = Request(url, headers={"User-Agent": "Mozilla/5.0"})
        with urlopen(request, timeout=12) as response:
            page = response.read(2_000_000).decode("utf-8", "replace")
            marker = "reCAPTCHA enabled" if re.search(r'recaptchaEnabled.{0,12}:\s*true', page) else ""
            return name, response.status, response.url, marker
    except HTTPError as error:
        return name, error.code, error.url, ""
    except Exception as error:
        return name, type(error).__name__, url, ""


def webdriver(path, body=None, method=None):
    request = Request(f"http://127.0.0.1:{PORT}{path}",
                      data=None if body is None else json.dumps(body).encode(),
                      headers={"Content-Type": "application/json"}, method=method)
    with urlopen(request, timeout=40) as response:
        return json.load(response)["value"]


def circle(address):
    driver = subprocess.Popen(
        ["/snap/bin/geckodriver", "--host", "127.0.0.1", "--port", str(PORT)],
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
    )
    session = None
    try:
        for _ in range(25):
            try:
                webdriver("/status")
                break
            except URLError:
                time.sleep(0.4)
        session = webdriver("/session", {"capabilities": {"alwaysMatch": {
            "browserName": "firefox",
            "moz:firefoxOptions": {
                "binary": "/snap/firefox/current/usr/lib/firefox/firefox",
                "args": ["-headless"],
            },
        }}})["sessionId"]
        base = "/session/" + session

        def execute(script):
            return webdriver(base + "/execute/sync", {"script": script, "args": []})

        webdriver(base + "/timeouts", {"pageLoad": 30000})
        webdriver(base + "/url", {"url": SITES["Circle"]})
        field = webdriver(base + "/element", {"using": "css selector", "value": 'input[name="address"]'})
        webdriver(base + "/element/" + next(iter(field.values())) + "/value", {"text": address})
        for _ in range(8):
            button = execute("""
                return Array.from(document.querySelectorAll('button[type="submit"]'))
                    .find(b => /Send 20 USDC/i.test(b.innerText) && !b.disabled) || null;
            """)
            if button:
                break
            time.sleep(1)
        else:
            print("Circle: Send 20 USDC remained disabled", flush=True)
            return
        print("Circle: submitting one normal Arc Testnet USDC claim", flush=True)
        webdriver(base + "/element/" + next(iter(button.values())) + "/click", {})
        for _ in range(22):
            result = execute(r"""
                const text = document.body.innerText.split("Frequently Asked Questions")[0];
                return {
                    tx: Array.from(document.querySelectorAll('a[href]'))
                        .map(a => a.href).find(h => /\/tx\/0x[0-9a-f]{64}/i.test(h)) || null,
                    alerts: Array.from(document.querySelectorAll('[role="alert"],[role="dialog"]'))
                        .filter(e => e.getClientRects().length).map(e => e.innerText).join(' '),
                    evidence: text.split('\n').filter(l => /verification failed|captcha failed|try again|limit exceeded|something went wrong|transaction hash|successfully|verification required/i.test(l) && l.length < 180),
                    challenge: Array.from(document.querySelectorAll('iframe[src*="bframe"]'))
                        .some(e => e.getClientRects().length && e.getBoundingClientRect().width > 0 &&
                            e.getBoundingClientRect().left >= 0 && e.getBoundingClientRect().left < innerWidth),
                };
            """)
            if result["tx"]:
                print("Circle: transaction link", result["tx"], flush=True)
                return
            if result["challenge"]:
                print("Circle: interactive reCAPTCHA challenge appeared", flush=True)
                return
            alerts = result["alerts"].strip()
            if alerts and re.search(r"error|failed|limit|verification|success", alerts, re.I):
                print("Circle:", re.sub(r"\s+", " ", alerts)[:240], flush=True)
                return
            messages = result["evidence"]
            if messages:
                print("Circle:", "; ".join(messages)[:240], flush=True)
                return
            time.sleep(2)
        print("Circle: no payout link or conclusive response after submission", flush=True)
    finally:
        if session:
            try:
                webdriver("/session/" + session, method="DELETE")
            except Exception:
                pass
        driver.terminate()
        driver.wait(timeout=10)


if __name__ == "__main__":
    with concurrent.futures.ThreadPoolExecutor(max_workers=6) as pool:
        for row in pool.map(probe, SITES.items()):
            print(*row, sep=" | ", flush=True)
    if len(sys.argv) == 3 and sys.argv[1] == "--claim-circle" and re.fullmatch(r"0x[0-9a-fA-F]{40}", sys.argv[2]):
        try:
            circle(sys.argv[2])
        except Exception as error:
            print(f"Circle browser failed ({type(error).__name__})", flush=True)
            sys.exit(1)
