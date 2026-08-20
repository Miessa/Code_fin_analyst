import json
import tempfile
import unittest
from pathlib import Path

from phase2.benchmark_engine import comparer
from phase2.derived_metrics import calculer_indicateurs
from phase2.pipeline import executer_phase2


REGISTRY = [
    {"cle": "cout_construction", "valeur": 1200, "description": "CAPEX"},
    {"cle": "investissement_total", "valeur": 2000, "description": "Investment"},
    {"cle": "gearing", "valeur": 0.75, "description": "Debt share"},
    {"cle": "tri_projet", "valeur": 0.12, "description": "Project IRR"},
    {"cle": "taux_actualisation", "valeur": 0.10, "description": "Discount rate"},
    {"cle": "duree_dette", "valeur": 18, "description": "Debt maturity"},
    {"cle": "duree_concession", "valeur": 35, "description": "Concession"},
]


class TestPhase2(unittest.TestCase):
    def test_derived_metrics(self):
        values = {x["cle"]: x["valeur"] for x in calculer_indicateurs(REGISTRY)}
        self.assertAlmostEqual(values["construction_share"], 0.6)
        self.assertAlmostEqual(values["equity_share"], 0.25)
        self.assertAlmostEqual(values["project_irr_spread"], 0.02)
        self.assertEqual(values["debt_tail"], 17)

    def test_unapproved_reference_cannot_issue_verdict(self):
        indicators = calculer_indicateurs(REGISTRY)
        refs = {"normes": [{"cle": "draft", "applies_to": "equity_share",
                            "low": .3, "high": .45, "unit": "ratio",
                            "source": "draft", "approved": False}]}
        result = comparer(indicators, refs)[0]
        self.assertEqual(result["status"], "NOT_COMPARABLE")
        self.assertIsNone(result["verdict"])

    def test_end_to_end_outputs(self):
        refs = {"_version": "test", "normes": [{
            "cle": "share", "applies_to": "construction_share", "low": .5,
            "high": .8, "unit": "ratio", "source": "test", "perimeter": "test",
            "approved": True}]}
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            registry_path, refs_path = root / "registry.json", root / "refs.json"
            registry_path.write_text(json.dumps(REGISTRY), encoding="utf-8")
            refs_path.write_text(json.dumps(refs), encoding="utf-8")
            result, json_path, md_path = executer_phase2(
                registry_path, refs_path, root / "outputs"
            )
            self.assertTrue(json_path.exists())
            self.assertTrue(md_path.exists())
            self.assertTrue((root / "outputs" / "analyse_financiere_phase2.docx").exists())
            self.assertEqual(result["comparaisons_benchmark"][0]["verdict"], "WITHIN")
            self.assertIn("tableau_benchmark_detaille", result)

    def test_point_reference_requires_matching_context(self):
        registry = REGISTRY + [
            {"cle": "puissance", "valeur": 1, "description": "Capacity"}
        ]
        indicators = calculer_indicateurs(registry, {
            "currency": "USD", "monetary_scale": 1000,
            "technology": "hydropower", "price_year": 2024,
        })
        refs = {"normes": [{
            "cle": "point", "applies_to": "capex_per_mw",
            "comparison_type": "point", "target": 1000000,
            "unit": "USD/MW", "technology": "hydropower",
            "currency": "USD", "price_year": 2024,
            "source": "test", "approved": True,
        }]}
        result = comparer(indicators, refs, {
            "currency": "USD", "benchmark_currency": "USD",
            "technology": "hydropower", "price_year": 2024,
        })[0]
        self.assertEqual(result["status"], "COMPARED")
        self.assertEqual(result["verdict"], "ABOVE_REFERENCE")


if __name__ == "__main__":
    unittest.main()
