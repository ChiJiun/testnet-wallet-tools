import subprocess
import sys


def logs(unit):
    return subprocess.check_output(
        ["journalctl", "-u", unit, "-n", "120", "--no-pager", "-o", "cat"],
        text=True,
    ).splitlines()


def needs_auth(unit, failed, restored):
    for line in reversed(logs(unit)):
        if failed in line:
            return True
        if restored in line:
            return False
    return False


issues = []
if needs_auth("google-sepolia-claim.service", "FAUCET_AUTH_REQUIRED", "Claim transaction:"):
    issues.append("Google Faucet: sign in again on the VM")
if needs_auth("celo-faucet.service", "Faucet HTTP 401", "claim confirmed:"):
    issues.append("Celo Faucet: update the API key on the VM")
if issues:
    sys.exit("; ".join(issues))
print("No faucet credentials require attention")
