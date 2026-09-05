import json
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path

from pydantic import ValidationError

from benchmark_bank.schemas import (
    BenchmarkBankDocument,
    IngestionRun,
    NormalizationEvent,
    Observation,
    Project,
    Source,
)
from benchmark_bank.schemas.export import export_json_schemas


NOW = datetime(2026, 8, 25, tzinfo=timezone.utc)


def source():
    return Source(
        source_id="worldbank_ppi",
        organization="World Bank",
        title="Private Participation in Infrastructure",
        source_type="structured_dataset",
        canonical_url="https://ppi.worldbank.org/",
    )


def run():
    return IngestionRun(
        ingestion_run_id="run:2026-08-25",
        source_id="worldbank_ppi",
        adapter_name="worldbank_ppi",
        adapter_version="1.0.0",
        status="succeeded",
        started_at=NOW,
        completed_at=NOW,
        records_read=1,
        records_accepted=1,
    )


def project():
    return Project(
        project_id="project:example_hydro",
        project_name="Example Hydropower Project",
        country_name="Cameroon",
        country_iso3="cmr",
        region="Sub-Saharan Africa",
        technology="hydropower",
    )


def observation():
    return Observation(
        observation_id="obs:investment",
        source_id="worldbank_ppi",
        project_id="project:example_hydro",
        ingestion_run_id="run:2026-08-25",
        metric="total_investment",
        raw_value=1450,
        raw_unit="USD million",
        normalized_value=1_450_000_000,
        normalized_unit="USD",
        currency="usd",
        price_year=2022,
        economic_perimeter="reported total project investment",
        estimate_stage="financial_close",
        source_location="PPI record WB-123",
    )


class TestBenchmarkBankSchemas(unittest.TestCase):
    def test_valid_document_and_normalization_lineage(self):
        obs = observation()
        event = NormalizationEvent(
            normalization_event_id="norm:investment_scale",
            ingestion_run_id=run().ingestion_run_id,
            observation_id=obs.observation_id,
            field_name="normalized_value",
            rule_id="rule:usd_million",
            rule_version="1.0",
            input_value=1450,
            output_value=1_450_000_000,
            formula="raw_value * 1_000_000",
        )
        bank = BenchmarkBankDocument(
            sources=[source()], projects=[project()], ingestion_runs=[run()],
            observations=[obs], normalization_events=[event],
        )
        self.assertEqual(bank.projects[0].country_iso3, "CMR")
        self.assertEqual(bank.observations[0].currency, "USD")

    def test_missing_cross_reference_is_rejected(self):
        with self.assertRaisesRegex(ValidationError, "unknown project"):
            BenchmarkBankDocument(
                sources=[source()], ingestion_runs=[run()], observations=[observation()]
            )

    def test_invalid_range_is_rejected(self):
        data = observation().model_dump()
        data.update(raw_value=None, raw_low=20, raw_high=10)
        with self.assertRaisesRegex(ValidationError, "raw_low"):
            Observation(**data)

    def test_derived_value_requires_formula_and_inputs(self):
        data = observation().model_dump()
        data.update(value_status="derived", derivation_formula=None, input_observation_ids=[])
        with self.assertRaisesRegex(ValidationError, "derived observations"):
            Observation(**data)

    def test_extra_fields_are_rejected(self):
        with self.assertRaises(ValidationError):
            Project(
                project_id="project:test", project_name="Test project",
                unexpected_field="not allowed",
            )

    def test_schema_export(self):
        with tempfile.TemporaryDirectory() as directory:
            paths = export_json_schemas(directory)
            self.assertEqual(len(paths), 6)
            document = json.loads((Path(directory) / "observation.schema.json").read_text())
            self.assertIn("observation_id", document["properties"])


if __name__ == "__main__":
    unittest.main()
