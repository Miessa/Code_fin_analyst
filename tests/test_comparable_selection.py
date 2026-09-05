import unittest

from benchmark_bank.analytics import (
    ComparableCandidate, ProjectFeatures, build_project_profile, review_candidates,
)


def feature(project_id):
    return ProjectFeatures(
        project_id=project_id, project_name=project_id, country_iso3="CMR",
        country_name="Cameroon", region="Sub-Saharan Africa",
        technology="hydropower", financial_close_year=2022,
        hydropower_configuration="conventional",
        project_status="Active", default_eligible=True, capacity_mw=500,
        investment_per_mw_usd=3_000_000, quality_score=1,
    )


class ComparableSelectionTests(unittest.TestCase):
    def test_profile_uses_generic_context_and_normalizes_percent_gearing(self):
        registry = [
            {"cle": "puissance", "valeur": 500, "unite": "MW"},
            {"cle": "duree_concession", "valeur": "35 ans", "unite": "ans"},
            {"cle": "gearing", "valeur": 75, "unite": "%"},
        ]
        result = build_project_profile(registry, {
            "project_name": "Kikot", "technology": "hydropower",
            "geography": "Cameroon", "data_year": 2024,
        })
        self.assertEqual(result.project_name, "Kikot")
        self.assertEqual(result.profile.country_iso3, "CMR")
        self.assertEqual(result.profile.hydropower_configuration, "conventional")
        self.assertEqual(result.profile.debt_share, 0.75)
        self.assertEqual(result.profile.contract_period_years, 35)

    def test_invalid_choice_stays_and_back_removes_previous_decision(self):
        candidates = [
            ComparableCandidate("a", "a", .9, "strong", features=feature("a")),
            ComparableCandidate("b", "b", .8, "strong", features=feature("b")),
        ]
        commands = iter(["bad", "a", "b", "r", "reason", "q"])
        messages = []
        result = review_candidates(
            candidates, target=2, minimum=1,
            input_fn=lambda prompt: next(commands), output_fn=messages.append,
        )
        self.assertTrue(any("Choix invalide" in x for x in messages))
        self.assertEqual(result["approved_count"], 0)
        self.assertEqual(result["decisions"][0]["decision"], "rejected")


if __name__ == "__main__":
    unittest.main()
