#!/usr/bin/env python3
"""Offline, provider-grounded faucet discovery and claim preparation."""
import argparse
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent


def entries():
    catalog = json.loads((ROOT / "faucet_catalog.json").read_text())
    circle = json.loads((ROOT / "faucets.json").read_text())
    result = []
    for source in catalog["sources"]:
        by_network = source.get("assets_by_network")
        if by_network:
            for network, token in by_network.items():
                result.append({"provider": source["name"], "network": network, "assets": [token], "url": source["url"], "mode": source["mode"], "eligibility": source.get("eligibility", "")})
        elif source["name"] == "Circle":
            for network in circle["circle_networks"]:
                result.append({"provider": "Circle", "network": network, "assets": ["USDC", "EURC", "cirBTC"], "availability": "unverified per token/network", "url": source["url"], "mode": source["mode"], "eligibility": source.get("eligibility", "")})
        else:
            result.append({"provider": source["name"], "network": "various (check website)", "assets": source.get("assets", []), "url": source["url"], "mode": source["mode"], "eligibility": source.get("eligibility", "")})
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--network", default="", help="Case-insensitive network filter")
    parser.add_argument("--token", default="", help="Case-insensitive asset filter")
    parser.add_argument("--provider", default="", help="Case-insensitive provider filter")
    parser.add_argument("--address", help="Public wallet address to display for manual claims")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()
    if args.address and (len(args.address) != 42 or not args.address.startswith("0x") or any(c not in "0123456789abcdefABCDEF" for c in args.address[2:])):
        parser.error("--address must be an EVM address (non-EVM networks need their native address format)")
    matches = [e for e in entries() if args.network.lower() in e["network"].lower() and args.token.lower() in ",".join(e["assets"]).lower() and args.provider.lower() in e["provider"].lower()]
    if args.json:
        print(json.dumps(matches, indent=2, ensure_ascii=False))
        return
    if args.address:
        print("Manual claim recipient:", args.address)
    for e in matches:
        print(f'{e["provider"]}: {e["network"]} | {", ".join(e["assets"])} | {e["url"]} | {e.get("availability", "check current availability")}')
    print(f"\n{len(matches)} catalog entries. No claims submitted. Follow each provider's limits and CAPTCHA.")


if __name__ == "__main__":
    main()
