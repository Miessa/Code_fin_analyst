import json
import tempfile
import unittest
from pathlib import Path

from arsel_core.orchestration import _profile_signature, sha256_file


class OrchestrationTests(unittest.TestCase):
    def test_hashes_are_deterministic_and_profile_order_independent(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "x.json"
            path.write_text("hello", encoding="utf-8")
            self.assertEqual(sha256_file(path), sha256_file(path))
        self.assertEqual(_profile_signature({"a": 1, "b": 2}), _profile_signature({"b": 2, "a": 1}))


if __name__ == "__main__": unittest.main()
