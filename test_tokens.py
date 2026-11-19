import unittest
from unittest.mock import patch
from eth_abi import encode
import tokens


class TokenTests(unittest.TestCase):
    def test_address_validation(self):
        with self.assertRaises(ValueError):
            tokens.valid_address("0x1234")

    def test_balance_selector(self):
        address = "0x" + "12" * 20
        with patch.object(tokens, "call", return_value="0x64") as call:
            self.assertEqual(tokens.token_balance("https://rpc.example", "0x" + "ab" * 20, address), 100)
            expected = "0x" + tokens.SELECTOR_BALANCE + encode(["address"], [address]).hex()
            self.assertEqual(call.call_args.args[2], expected)

    def test_decimals_guard(self):
        with patch.object(tokens, "call", return_value="0x25"):
            with self.assertRaisesRegex(ValueError, "Unexpected"):
                tokens.token_decimals("https://rpc.example", "0x" + "ab" * 20)


if __name__ == "__main__":
    unittest.main()
