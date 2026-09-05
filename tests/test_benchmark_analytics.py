import unittest

from benchmark_bank.analytics import (
    ProjectFeatures, ProjectProfile, calculate_benchmark_statistics, rank_comparables,
)


def feature(project_id, **values):
    defaults = dict(
        project_id=project_id, project_name=project_id, country_iso3=None,
        country_name=None, region="Sub-Saharan Africa", technology="hydropower",
        hydropower_configuration="conventional",
        financial_close_year=2022, project_status="Active", default_eligible=True,
        investment_usd=300_000_000, capacity_mw=100,
        investment_per_mw_usd=3_000_000, investment_per_kw_usd=3000,
        quality_score=1.0,
    )
    defaults.update(values)
    return ProjectFeatures(**defaults)


class BenchmarkAnalyticsTests(unittest.TestCase):
    def test_ranking_hard_filters_technology_and_penalizes_historical(self):
        profile = ProjectProfile(
            technology="hydropower", hydropower_configuration="conventional",
            region="Sub-Saharan Africa",
            capacity_mw=100, financial_close_year=2024,
        )
        exact = feature("exact")
        old = feature("old", default_eligible=False, financial_close_year=2010)
        solar = feature("solar", technology="solar_pv")
        too_small = feature("small", capacity_mw=10)
        pumped = feature("pumped", hydropower_configuration="pumped_storage")
        ranked = rank_comparables(profile, [old, solar, too_small, pumped, exact])
        self.assertEqual([item.project_id for item in ranked], ["exact", "old"])
        self.assertIn("historical or non-active fallback", ranked[1].warnings)

    def test_metric_specific_statistics_keep_sample_size(self):
        first = feature("a", debt_share=0.7)
        second = feature("b", investment_per_mw_usd=5_000_000, debt_share=None)
        result = calculate_benchmark_statistics(
            [first, second], ["investment_per_mw_usd", "debt_share"]
        )
        self.assertEqual(result[0].sample_size, 2)
        self.assertEqual(result[0].median, 4_000_000)
        self.assertEqual(result[1].sample_size, 1)


if __name__ == "__main__":
    unittest.main()
