import unittest
from evaluation.benchmark_pipeline import construire_resume
from arsel_core.llm_instrumentation import InstrumentationLLM


class TestBenchmarkPipeline(unittest.TestCase):
    def test_resume_end_to_end(self):
        details = [
            {"retrieval_rank": 2, "structural_rank": 1,
             "final_outcome": "SELECTED", "final_correct": True,
             "deterministic_fallback_correct": True},
            {"retrieval_rank": 12, "structural_rank": 3,
             "final_outcome": "AMBIGUOUS", "final_correct": False,
             "deterministic_fallback_correct": False},
            {"retrieval_rank": None, "structural_rank": None,
             "final_outcome": "NO_MATCH", "final_correct": False,
             "deterministic_fallback_correct": False},
        ]
        resume = construire_resume(details, InstrumentationLLM(), 1.25)
        self.assertAlmostEqual(resume["retrieval_recall@5"], 1 / 3)
        self.assertAlmostEqual(resume["structural_recall@5"], 2 / 3)
        self.assertEqual(resume["automatic_selection_accuracy"], 1.0)
        self.assertAlmostEqual(resume["deterministic_fallback_accuracy"], 1 / 3)
        self.assertAlmostEqual(resume["ambiguity_rate"], 1 / 3)


if __name__ == "__main__": unittest.main()
