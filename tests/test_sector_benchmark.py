import unittest

from phase2.sector_benchmark import enrich_sector_table, position_against_irena


class SectorBenchmarkTests(unittest.TestCase):
    def test_positions_only_unit_compatible_project_values(self):
        sector = {"status":"APPLIED", "references":[
            {"metric":"capacity_factor", "value":.48, "unit":"ratio", "geography":"global"},
            {"metric":"lcoe", "value":.057, "unit":"2024 USD/kWh", "geography":"global"},
        ]}
        result = position_against_irena(sector, [], [{"cle":"capacity_factor", "valeur":.60}], {})
        by_metric = {item["metric"]:item for item in result["comparisons"]}
        self.assertEqual(by_metric["capacity_factor"]["position"], "ABOVE")
        self.assertTrue(by_metric["capacity_factor"]["comparable"])
        self.assertEqual(by_metric["lcoe"]["position"], "CONTEXT_ONLY")

    def test_active_sector_reference_replaces_static_table_value(self):
        rows = [{"cout":"Facteur de charge", "valeurs_standards":"ancien"}]
        sector = {"references":[{"metric":"capacity_factor", "value":.48, "unit":"ratio",
                                 "source_location":"Workbook sheet 'Table S.1', G9"}]}
        enriched = enrich_sector_table(rows, sector)
        self.assertIn("48.0 %", enriched[0]["valeurs_standards"])
        self.assertIn("Table S.1", enriched[0]["valeurs_standards"])


if __name__ == "__main__": unittest.main()
