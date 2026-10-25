"""Verification code extraction ignores links, years and stale or unrelated mail."""
import sys
import unittest
from datetime import datetime, timedelta, timezone

from browser_test_support import HERE

sys.path.insert(0, str(HERE))
import verification_code as vc


class ExtractCodeTests(unittest.TestCase):
    def test_numeric_code_after_label(self):
        self.assertEqual(vc.extract_code("Your verification code", "Hello,\nYour verification code is 483920.\nThanks"), "483920")

    def test_code_on_next_line(self):
        self.assertEqual(vc.extract_code("Sign in", "Use this one-time code:\n731 204\nIt expires soon."), "731204")

    def test_links_and_years_are_ignored(self):
        body = "Verify your account: https://x.example.com/verify?t=123456789\nCopyright 2026 Citi"
        self.assertIsNone(vc.extract_code("Welcome", body))

    def test_repeated_digit_noise_is_not_a_code(self):
        self.assertIsNone(vc.extract_code("Your code", "Code: 000000"))

    def test_alphanumeric_code(self):
        self.assertEqual(vc.extract_code("Confirm", "Your security code is A7K2M9"), "A7K2M9")

    def test_plain_words_are_not_codes(self):
        self.assertIsNone(vc.extract_code("Your code", "Your code is SUBMIT"))


class GateTests(unittest.TestCase):
    def test_fresh_and_stale(self):
        now = datetime(2026, 10, 25, 12, 0, tzinfo=timezone.utc)
        self.assertTrue(vc.fresh_enough(now - timedelta(minutes=5), now))
        self.assertFalse(vc.fresh_enough(now - timedelta(minutes=30), now))
        self.assertFalse(vc.fresh_enough(now + timedelta(minutes=1), now))

    def test_sender_domain_must_match_exactly_or_subdomain(self):
        allowed = ["myworkday.com", "citi.com"]
        self.assertTrue(vc.sender_allowed("Citi <no-reply@mail.citi.com>", allowed))
        self.assertTrue(vc.sender_allowed("x@myworkday.com", allowed))
        self.assertFalse(vc.sender_allowed("x@evilciti.com", allowed))
        self.assertFalse(vc.sender_allowed("", allowed))


if __name__ == "__main__":
    unittest.main()
