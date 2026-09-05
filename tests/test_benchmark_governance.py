import unittest

from benchmark_bank.governance import QualityPolicy, assess_quality, compare_snapshots


class Report:
    default_eligible_projects = 8


class Issue:
    def __init__(self, code, field): self.code, self.field = code, field


class Feature:
    def __init__(self, usable=True, issues=None):
        self.investment_per_mw_usd = 1 if usable else None
        self.issues = issues or []


class BenchmarkGovernanceTests(unittest.TestCase):
    def test_change_log_separates_added_removed_modified(self):
        result = compare_snapshots(
            {"project":{"a":"1","b":"1"}}, {"project":{"b":"2","c":"1"}}
        )["project"]
        self.assertEqual(result["added"], ["c"])
        self.assertEqual(result["removed"], ["a"])
        self.assertEqual(result["modified"], ["b"])

    def test_quality_filters_are_metric_specific_and_gated(self):
        features = [Feature() for _ in range(8)] + [
            Feature(False, [Issue("ambiguous_multiple_values", "investment_commitment")]),
            Feature(False),
        ]
        policy = QualityPolicy(5, 5, .7, .2, .2)
        quality = assess_quality(Report(), features, {"project":{"removed":[],"modified":[],"unchanged_count":10}}, policy)
        self.assertTrue(quality["passed"])
        self.assertEqual(quality["measures"]["investment_per_mw_coverage"], .8)
        self.assertIn("plausibility_ranges", quality["filters"])
        self.assertEqual(quality["measures"]["sector_statistics_count"], 0)

    def test_planned_unclassified_exclusions_do_not_weaken_removal_gate(self):
        features = [Feature() for _ in range(10)]
        changes = {"project": {"removed": ["planned", "unexpected"], "modified": [],
                               "unchanged_count": 8}}
        policy = QualityPolicy(5, 5, .7, .2, .15)
        quality = assess_quality(Report(), features, changes, policy,
                                 expected_project_removals={"planned"})
        self.assertTrue(quality["passed"])
        self.assertEqual(quality["measures"]["intentional_project_exclusions"], 1)
        self.assertEqual(quality["measures"]["unexpected_project_removals"], 1)


if __name__ == "__main__": unittest.main()
