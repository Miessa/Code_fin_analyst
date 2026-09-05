import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path

from benchmark_bank.schemas import (
    BenchmarkBankDocument,
    IngestionRun,
    NormalizationEvent,
    Observation,
    Project,
    Source,
)
from benchmark_bank.storage import BenchmarkRepository


NOW = datetime(2026, 8, 25, tzinfo=timezone.utc)


def entities():
    source = Source(
        source_id="worldbank_ppi", organization="World Bank",
        title="PPI", source_type="structured_dataset",
    )
    project = Project(
        project_id="project:hydro", project_name="Hydro Project",
        country_iso3="CMR", region="Sub-Saharan Africa", technology="hydropower",
    )
    run = IngestionRun(
        ingestion_run_id="run:001", source_id=source.source_id,
        adapter_name="worldbank_ppi", adapter_version="1.0", status="succeeded",
        started_at=NOW, completed_at=NOW, records_read=1, records_accepted=1,
    )
    observation = Observation(
        observation_id="obs:investment", source_id=source.source_id,
        project_id=project.project_id, ingestion_run_id=run.ingestion_run_id,
        metric="total_investment", raw_value="USD 100 million",
        raw_unit="USD million", normalized_value=100_000_000,
        normalized_unit="USD", currency="USD", source_location="record 1",
        review_status="verified",
    )
    event = NormalizationEvent(
        normalization_event_id="norm:001", ingestion_run_id=run.ingestion_run_id,
        observation_id=observation.observation_id, field_name="normalized_value",
        rule_id="rule:scale", rule_version="1.0", input_value=100,
        output_value=100_000_000,
    )
    return source, project, run, observation, event


class TestBenchmarkRepository(unittest.TestCase):
    def test_initializes_migrations_and_empty_views(self):
        with BenchmarkRepository(":memory:") as repository:
            self.assertEqual(repository.counts()["project"], 0)
            self.assertEqual(
                repository.connection.execute("SELECT version FROM schema_migrations").fetchone()[0],
                1,
            )

    def test_atomic_document_load_and_queries(self):
        source, project, run, observation, event = entities()
        document = BenchmarkBankDocument(
            sources=[source], projects=[project], ingestion_runs=[run],
            observations=[observation], normalization_events=[event],
        )
        with BenchmarkRepository(":memory:") as repository:
            results = repository.load_document(document)
            self.assertEqual(len(results), 5)
            self.assertTrue(all(result.changed for result in results))
            self.assertEqual(repository.get_project(project.project_id), project)
            self.assertEqual(
                repository.query_projects(technology="hydropower")[0].project_id,
                project.project_id,
            )
            self.assertEqual(
                repository.query_observations(metric="total_investment", normalized_only=True)[0],
                observation,
            )

    def test_identical_upsert_is_idempotent_and_change_creates_revision(self):
        source, *_ = entities()
        with BenchmarkRepository(":memory:") as repository:
            first = repository.upsert_source(source)
            repeated = repository.upsert_source(source)
            changed = source.model_copy(update={"notes": "updated evidence"})
            third = repository.upsert_source(changed)
            history = repository.history("source", source.source_id)
            self.assertEqual((first.revision, first.changed), (1, True))
            self.assertEqual((repeated.revision, repeated.changed), (1, False))
            self.assertEqual((third.revision, third.changed), (2, True))
            self.assertEqual(len(history), 2)
            self.assertFalse(history[0].is_current)
            self.assertTrue(history[1].is_current)
            self.assertEqual(repository.get_source(source.source_id).notes, "updated evidence")

    def test_direct_insert_enforces_database_references(self):
        _, _, _, observation, _ = entities()
        with BenchmarkRepository(":memory:") as repository:
            with self.assertRaisesRegex(ValueError, "unknown source_id"):
                repository.upsert_observation(observation)
            self.assertEqual(repository.counts()["observation"], 0)

    def test_database_persists_between_connections(self):
        source, *_ = entities()
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "bank.duckdb"
            with BenchmarkRepository(path) as repository:
                repository.upsert_source(source)
            with BenchmarkRepository(path) as repository:
                self.assertEqual(repository.get_source(source.source_id), source)


if __name__ == "__main__":
    unittest.main()
