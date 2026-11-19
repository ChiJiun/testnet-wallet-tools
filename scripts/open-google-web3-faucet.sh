#!/usr/bin/env bash
set -euo pipefail
umask 077
url=https://cloud.google.com/application/web3/faucet/ethereum/sepolia
if [[ -x /snap/bin/firefox ]]; then
    browser=/snap/bin/firefox
    profile="$HOME/snap/firefox/common/web3-faucet-profile"
else
    browser=$(command -v firefox) || { echo 'Firefox is required.' >&2; exit 1; }
    profile="$HOME/.local/share/web3-faucet/firefox-profile"
fi
mkdir -p -- "$profile"
chmod 700 -- "$profile"
exec "$browser" --no-remote --profile "$profile" "$url"
