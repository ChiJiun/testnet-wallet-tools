#!/usr/bin/env bash
set -euo pipefail
cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.."
git check-ignore -q -- .env || { echo '.env must be ignored by Git.' >&2; exit 1; }
if [[ -e .env || -L .env ]]; then
    echo '.env already exists. It has been left in place.' >&2
    exit 1
fi
read -r -s -p 'Celo Faucet API key: ' key </dev/tty
printf '\n'
if [[ ! $key =~ ^[A-Za-z0-9._~+/=-]+$ ]]; then
    echo 'Invalid or empty key.' >&2
    exit 1
fi
umask 077
set -o noclobber
printf 'CELO_FAUCET_API_KEY=%s\n' "$key" > .env
unset key
echo 'Saved .env with permissions 600.'
