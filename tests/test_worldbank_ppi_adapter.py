import unittest

import pandas as pd

from benchmark_bank.sources.worldbank_ppi import REQUIRED_COLUMNS, WorldBankPPIAdapter


def row(**updates):
    values = {column: None for column in REQUIRED_COLUMNS}
    values.update({
        "ID": 1,
        "name": "Recent Solar Project",
        "sector": "Energy",
        "country": "Cameroon",
        "Region": "AFR",
        "FCY": 2022,
        "type": "Greenfield project",
        "stype": "Build, operate, and transfer",
        "status_n": "Active",
        "period": 25,
        "private": 75,
        "fees": 0,
        "physical": 90,
        "investment": 100,
        "capacity": "MW",
        "pcapacity": 50,
        "technol": "Solar PV",
        "PRS": "Purchase Agreements (private & public)",
        "OSR": "N/A",
        "FundingYear": 2022,
        "debt": 70,
        "equity": "30",
        "IY": 2022,
        "Description": "Utility-scale solar project",
    })
    values.update(updates)
    return values


class TestWorldBankPPIAdapter(unittest.TestCase):
    def test_energy_only_recent_cohort_and_exact_row_deduplication(self):
        frame = pd.DataFrame([
            row(),
            row(),  # repeated characteristic row: identical observations
            row(
                ID=2, name="Older Hydro", FCY=2018, IY=2018,
                technol="Large Hydro (>50MW)", pcapacity=192,
                investment=500, physical=480, debt=None, equity=".",
            ),
            row(ID=3, name="Toll Road", sector="Transport", technol="NA"),
        ])
        adapter = WorldBankPPIAdapter("synthetic.dta", recent_from_year=2020)
        document, report = adapter.build_from_dataframe(frame, checksum="a" * 64)

        self.assertEqual(report.rows_read, 4)
        self.assertEqual(report.energy_rows, 3)
        self.assertEqual(report.unique_energy_projects, 2)
        self.assertEqual(report.recent_projects, 1)
        self.assertEqual(report.default_eligible_projects, 1)
        self.assertEqual(report.older_fallback_projects, 1)
        self.assertEqual(len(document.projects), 2)
        recent = next(x for x in document.projects if x.project_id == "worldbank_ppi:1")
        older = next(x for x in document.projects if x.project_id == "worldbank_ppi:2")
        self.assertTrue(recent.metadata["default_comparable_eligible"])
        self.assertFalse(older.metadata["default_comparable_eligible"])
        self.assertEqual(recent.technology, "solar_pv")
        self.assertEqual(older.technology, "hydropower")
        investments = [x for x in document.observations if x.metric == "investment_commitment"]
        self.assertEqual(len(investments), 2)
        self.assertEqual(report.normalization_event_count, len(document.normalization_events))
        self.assertTrue(any(
            event.rule_id == "rule:usd_million_to_usd"
            for event in document.normalization_events
        ))

    def test_cancelled_recent_project_is_not_default_eligible(self):
        frame = pd.DataFrame([row(status_n="Cancelled")])
        document, report = WorldBankPPIAdapter("synthetic.dta").build_from_dataframe(
            frame, checksum="b" * 64
        )
        self.assertEqual(report.recent_projects, 1)
        self.assertEqual(report.default_eligible_projects, 0)
        self.assertFalse(document.projects[0].metadata["default_comparable_eligible"])

    def test_unclassified_energy_project_is_completely_excluded(self):
        frame = pd.DataFrame([row(technol=None), row(ID=2, technol="NA")])
        document, report = WorldBankPPIAdapter("synthetic.dta").build_from_dataframe(
            frame, checksum="d" * 64
        )
        self.assertFalse(document.projects)
        self.assertFalse(document.observations)
        self.assertEqual(report.unclassified_projects_excluded, 2)
        self.assertEqual(report.unclassified_rows_excluded, 2)
        self.assertEqual(report.unique_energy_projects, 0)

    def test_missing_official_column_fails_loudly(self):
        frame = pd.DataFrame([row()]).drop(columns=["investment"])
        with self.assertRaisesRegex(ValueError, "investment"):
            WorldBankPPIAdapter("synthetic.dta").build_from_dataframe(
                frame, checksum="c" * 64
            )


if __name__ == "__main__":
    unittest.main()
