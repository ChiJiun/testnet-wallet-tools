#!/usr/bin/env python3
"""Generate a test-only BIP39 mnemonic without printing secret material."""
import os
from pathlib import Path
from mnemonic import Mnemonic


def main():
    target = Path(__file__).resolve().parent / 'secrets' / 'mnemonic.txt'
    target.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    os.chmod(target.parent, 0o700)
    phrase = Mnemonic('english').generate(strength=256)
    assert Mnemonic('english').check(phrase)
    fd = os.open(target, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(fd, 'w') as f:
        f.write(phrase + '\n')
    print('Generated 24-word BIP39 mnemonic at:', target)
    print('Mnemonic contents intentionally not displayed. TESTNET ONLY.')


if __name__ == '__main__':
    main()
