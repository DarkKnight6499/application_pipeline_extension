"""Author: Yazad Madan. Browser-free assist behavior and worker boundary checks."""
import shutil
import subprocess
import unittest
from pathlib import Path

# Config
NODE = shutil.which("node")
HARNESS = Path(__file__).with_name("assist_content_harness.js")


@unittest.skipUnless(NODE, "Node.js is required for browser-free assist checks.")
class AssistContentTests(unittest.TestCase):
    def test_checkbox_click_and_verification(self):
        result = subprocess.run([NODE, str(HARNESS), "--checkboxes"], capture_output=True, text=True, timeout=15)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("Checkbox regression checks passed", result.stdout)

    def test_plain_forms_and_profile_signature(self):
        result = subprocess.run([NODE, str(HARNESS), "--plain-forms"], capture_output=True, text=True, timeout=15)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("Plain form regression checks passed", result.stdout)
        self.assertIn("Worker regression checks passed", result.stdout)

    def test_synthetic_controls_and_worker(self):
        result = subprocess.run([NODE, str(HARNESS)], capture_output=True, text=True, timeout=15)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("Assist content and worker checks passed", result.stdout)


if __name__ == "__main__":
    unittest.main()
