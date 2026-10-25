"""Credential store round-trips through an injected backend and never needs a file."""
import sys
import unittest

from browser_test_support import HERE

sys.path.insert(0, str(HERE))
import credential_store as store


class FakeKeyring:
    def __init__(self):
        self.items = {}

    def set_password(self, service, account, password):
        self.items[(service, account)] = password

    def get_password(self, service, account):
        return self.items.get((service, account))


class CredentialStoreTests(unittest.TestCase):
    def test_round_trip_is_case_insensitive_on_host(self):
        backend = FakeKeyring()
        store.save_login("Citi.WD5.myworkdayjobs.com", "a@example.com", "pw1", backend)
        self.assertEqual(store.get_login("citi.wd5.myworkdayjobs.com", backend), ("a@example.com", "pw1"))

    def test_missing_host_returns_none(self):
        self.assertIsNone(store.get_login("none.example.com", FakeKeyring()))

    def test_hosts_are_separate(self):
        backend = FakeKeyring()
        store.save_login("a.example.com", "u", "pa", backend)
        store.save_login("b.example.com", "u", "pb", backend)
        self.assertEqual(store.get_login("b.example.com", backend)[1], "pb")

    def test_empty_fields_are_refused(self):
        with self.assertRaises(ValueError):
            store.save_login("a.example.com", "", "pw", FakeKeyring())


if __name__ == "__main__":
    unittest.main()
