#!/usr/bin/env python3
import subprocess
import sys
from datetime import datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

zone = ZoneInfo("Asia/Taipei")
now = datetime.now(zone)
scheduled = now.replace(hour=9, minute=0, second=0, microsecond=0)
if now < scheduled + timedelta(minutes=15):
    scheduled -= timedelta(days=1)

if subprocess.run(["systemctl", "is-active", "--quiet", "celo-faucet.timer"]).returncode:
    sys.exit("Celo faucet timer is inactive")

result = subprocess.check_output(
    ["systemctl", "show", "-p", "Result", "--value", "celo-faucet.service"], text=True
).strip()
if result != "success":
    sys.exit(f"Celo faucet service failed: {result}")

stamp = Path("/var/lib/celo-faucet/last-success")
try:
    completed = stamp.stat().st_mtime
except FileNotFoundError:
    completed = 0
if completed < scheduled.timestamp():
    sys.exit("Celo faucet missed its daily confirmation deadline")
print("Celo faucet watchdog OK")
