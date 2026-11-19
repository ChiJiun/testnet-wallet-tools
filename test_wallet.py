import unittest
from unittest.mock import patch
import wallet


class WalletTests(unittest.TestCase):
    def test_addresses_are_distinct(self):
        accounts = wallet.wallets(3)
        self.assertEqual(len({a.address for a in accounts}), 3)

    def test_rpc_chain_id_guard(self):
        with patch.dict("os.environ", {"RPC_SEPOLIA": "https://example.org"}):
            with patch.object(wallet, "rpc", return_value=hex(1)):
                with self.assertRaisesRegex(ValueError, "Chain ID mismatch"):
                    wallet.network("sepolia")

    def test_rpc_rejects_insecure_url(self):
        with self.assertRaisesRegex(ValueError, "HTTPS"):
            wallet.rpc("http://example.org", "eth_chainId")


if __name__ == "__main__":
    unittest.main()
