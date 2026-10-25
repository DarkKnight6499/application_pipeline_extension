"""Picker aliases keep an ordered, de-duplicated name list and match on exact normalized text."""
import sys
import tempfile
import unittest

from browser_test_support import HERE

sys.path.insert(0, str(HERE))
import picker_aliases as aliases


class PickerAliasTests(unittest.TestCase):
    def fresh(self):
        return {"schema_version": 1, "entities": {}}

    def test_canonical_first_and_duplicates_dropped(self):
        data = self.fresh()
        aliases.set_entity(data, "school", "Rutgers University - Newark", ["Rutgers Newark", "rutgers newark", "Rutgers Newark"], "Rutgers")
        names, fallback = aliases.candidates_for(data, "school", "Rutgers Newark")
        self.assertEqual(names, ["Rutgers University - Newark", "Rutgers Newark"])
        self.assertEqual(fallback, "Rutgers")

    def test_unknown_value_is_tried_as_is(self):
        self.assertEqual(aliases.candidates_for(self.fresh(), "school", "Some College"), (["Some College"], "Some College"))

    def test_kinds_are_separate(self):
        data = self.fresh()
        aliases.set_entity(data, "school", "Rutgers Newark", [])
        self.assertEqual(aliases.candidates_for(data, "field", "Rutgers Newark")[0], ["Rutgers Newark"])

    def test_empty_is_refused(self):
        self.assertFalse(aliases.set_entity(self.fresh(), "school", "", []))

    def test_list_is_capped_at_ten(self):
        data = self.fresh()
        aliases.set_entity(data, "school", "A0", [f"A{i}" for i in range(1, 20)])
        self.assertEqual(len(aliases.candidates_for(data, "school", "A0")[0]), 10)

    def test_learn_adds_a_portal_label_once(self):
        data = self.fresh()
        aliases.set_entity(data, "school", "Rutgers Newark", [])
        self.assertTrue(aliases.learn_name(data, "school", "Rutgers Newark", "Rutgers U Newark Campus"))
        self.assertFalse(aliases.learn_name(data, "school", "Rutgers Newark", "rutgers u newark campus"))
        self.assertFalse(aliases.learn_name(data, "school", "Unknown", "x"))
        self.assertEqual(aliases.candidates_for(data, "school", "Rutgers Newark")[0][-1], "Rutgers U Newark Campus")

    def test_round_trip(self):
        with tempfile.TemporaryDirectory() as folder:
            data = aliases.load_aliases(folder)
            aliases.set_entity(data, "school", "Rutgers Newark", ["Rutgers"], "Rutgers")
            aliases.save_aliases(data, folder)
            self.assertEqual(aliases.candidates_for(aliases.load_aliases(folder), "school", "rutgers")[1], "Rutgers")


if __name__ == "__main__":
    unittest.main()


class ProfilePickersTests(unittest.TestCase):
    def test_profile_pickers_lists_names_and_fallback_per_kind(self):
        data = aliases.load_aliases(tempfile.mkdtemp())
        aliases.set_entity(data, "school", "Rutgers University - Newark", ["Rutgers Newark"], fallback="Rutgers")
        entry = aliases.profile_pickers(data)["school"][0]
        self.assertEqual((entry["names"], entry["fallback"]), (["Rutgers University - Newark", "Rutgers Newark"], "Rutgers"))
