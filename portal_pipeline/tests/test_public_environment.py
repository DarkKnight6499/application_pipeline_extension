"""Public discovery does not silently require another candidate checkout."""
import os
import tempfile
import unittest
from unittest.mock import patch

from test_support import workflow_source

# Test configuration
SOURCE_ENVIRONMENT = "PORTAL_SOURCE"


class PublicEnvironmentTests(unittest.TestCase):
    def test_missing_optional_source_returns_none(self):
        with patch.dict(os.environ, {}, clear=True):
            self.assertIsNone(workflow_source())

    def test_explicit_invalid_source_is_configuration_error(self):
        with tempfile.TemporaryDirectory() as temporary:
            with patch.dict(os.environ, {SOURCE_ENVIRONMENT: temporary}, clear=True):
                with self.assertRaises(RuntimeError):
                    workflow_source()


if __name__ == "__main__":
    unittest.main()
