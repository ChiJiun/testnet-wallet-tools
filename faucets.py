#!/usr/bin/env python3
"""List verified faucet entry points; no automated claiming or CAPTCHA bypass."""
import argparse
import json
from pathlib import Path

def main():
    p = argparse.ArgumentParser()
    p.add_argument("--network", help="Case-insensitive substring of network name")
    p.add_argument("--json", action="store_true")
    args = p.parse_args()
    data = json.loads((Path(__file__).parent / "faucets.json").read_text())
    matching = [x for x in data["circle_networks"] if not args.network or args.network.lower() in x.lower()]
    if args.json:
        print(json.dumps({"circle_networks": matching, "assets": data["assets"], "providers": data["providers"]}, indent=2))
        return
    print("Circle networks (token availability depends on chain):")
    for chain in matching:
        print(" -", chain)
    print("\nFaucet providers:")
    for provider in data["providers"]:
        print(f" - {provider['name']}: {provider['url']} ({provider['description']})")
    print("\nUse each provider's UI and comply with rate limits; no automated claims.")

if __name__ == "__main__":
    main()
