import json
import tempfile
import unittest
from pathlib import Path

from benchmark_hybrid.llm_extractor import ResilientLLMExtractor
from benchmark_hybrid.validator import validate_observation


class TestHybridBenchmark(unittest.TestCase):
    def test_reference_integrity(self):
        path = Path("benchmark_hybrid/data/referentiel_normes.json")
        data = json.loads(path.read_text(encoding="utf-8"))
        sources = {x["source_id"] for x in data["sources"]}
        observations = {x["observation_id"] for x in data["observations"]}
        self.assertTrue(all(x["source_id"] in sources for x in data["observations"]))
        self.assertTrue(all(x["observation_id"] in observations for x in data["comparison_rules"]))
        self.assertGreaterEqual(len(data["observations"]), 25)
        self.assertGreaterEqual(len(data["projects"]), 3)
        for project in data["projects"]:
            self.assertIn(project["source_id"], sources)
            self.assertGreaterEqual(len(project["metrics"]), 3)
            self.assertTrue(all(
                metric["observation_id"] in observations
                for metric in project["metrics"].values()
            ))

    def test_numeric_evidence_validation(self):
        result = validate_observation(
            {"metric": "minimum_dscr", "value": 1.47, "unit": "x"},
            "The minimum DSCR is 1.47x."
        )
        self.assertTrue(result["valid"])

    def test_503_retry_then_checkpoint(self):
        calls = {"count": 0}
        def flaky(_):
            calls["count"] += 1
            if calls["count"] == 1:
                raise RuntimeError("503 service unavailable")
            return {"observations": []}
        with tempfile.TemporaryDirectory() as directory:
            extractor = ResilientLLMExtractor(
                Path(directory) / "checkpoint.json", attempts=2, call=flaky
            )
            result = extractor.extract("source", [{"text": "DSCR 1.47x"}])
            self.assertEqual(result["status"], "SUCCESS")
            self.assertEqual(calls["count"], 2)
            extractor.extract("source", [])
            self.assertEqual(calls["count"], 2)


if __name__ == "__main__":
    unittest.main()
