"""Author: Yazad Madan. Browser-free checks for assist injection boundaries."""
import json
import unittest
from pathlib import Path
from urllib.parse import urlsplit

# Config
EXTENSION = Path(__file__).resolve().parents[1] / "extension"
EXPECTED_HOSTS = {"*.myworkdayjobs.com", "*.myworkdaysite.com", "boards.greenhouse.io",
    "job-boards.greenhouse.io", "*.greenhouse.io", "jobs.lever.co", "*.ashbyhq.com", "*.icims.com",
    "*.successfactors.com", "*.successfactors.eu", "*.oraclecloud.com", "*.smartrecruiters.com",
    "*.taleo.net", "*.jobvite.com", "*.paylocity.com", "*.paycomonline.net", "*.dayforcehcm.com",
    "*.ultipro.com", "*.adp.com"}


class AssistManifestTests(unittest.TestCase):
    def test_assist_matches_are_only_named_application_hosts(self):
        manifest = json.loads((EXTENSION / "manifest.json").read_text())
        self.assertEqual(manifest["host_permissions"], ["http://127.0.0.1/*"])
        scripts = manifest["content_scripts"]
        self.assertEqual(len(scripts), 1)
        self.assertEqual(scripts[0]["js"], ["assist-content.js"])
        matches = scripts[0]["matches"]
        self.assertNotIn("<all_urls>", json.dumps(manifest))
        self.assertEqual({urlsplit(pattern).netloc for pattern in matches}, EXPECTED_HOSTS)
        self.assertTrue(all(urlsplit(pattern).scheme == "https" for pattern in matches))
        self.assertTrue(all(urlsplit(pattern).netloc != "*" for pattern in matches))
        self.assertNotIn("externally_connectable", manifest)
        self.assertNotIn("web_accessible_resources", manifest)


if __name__ == "__main__":
    unittest.main()
