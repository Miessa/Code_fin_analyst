"""Versioned DuckDB repository for canonical benchmark-bank models."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Generic, Iterable, TypeVar

import duckdb
from pydantic import BaseModel

from benchmark_bank.schemas import (
    BenchmarkBankDocument,
    IngestionRun,
    NormalizationEvent,
    Observation,
    Project,
    Source,
)
from .migrations import MIGRATIONS


ModelT = TypeVar("ModelT", bound=BaseModel)


@dataclass(frozen=True)
class UpsertResult:
    entity_type: str
    entity_id: str
    revision: int
    changed: bool


@dataclass(frozen=True)
class Revision(Generic[ModelT]):
    revision: int
    is_current: bool
    content_hash: str
    recorded_at: datetime
    model: ModelT


@dataclass(frozen=True)
class _EntityConfig:
    name: str
    table: str
    id_field: str
    model: type[BaseModel]
    projected_fields: tuple[str, ...]


CONFIGS = {
    "source": _EntityConfig(
        "source", "bank_sources", "source_id", Source,
        ("organization", "source_type", "publication_date", "review_status"),
    ),
    "project": _EntityConfig(
        "project", "bank_projects", "project_id", Project,
        ("project_name", "country_iso3", "region", "technology", "project_type",
         "revenue_model", "identity_status"),
    ),
    "ingestion_run": _EntityConfig(
        "ingestion_run", "bank_ingestion_runs", "ingestion_run_id", IngestionRun,
        ("source_id", "adapter_name", "adapter_version", "status", "started_at", "completed_at"),
    ),
    "observation": _EntityConfig(
        "observation", "bank_observations", "observation_id", Observation,
        ("source_id", "project_id", "ingestion_run_id", "metric", "observation_type",
         "value_status", "raw_value_numeric", "raw_value_text", "raw_low", "raw_high",
         "raw_unit", "normalized_value", "normalized_low", "normalized_high",
         "normalized_unit", "currency", "price_year", "statistic", "economic_perimeter",
         "quality_level", "review_status"),
    ),
    "normalization_event": _EntityConfig(
        "normalization_event", "bank_normalization_events", "normalization_event_id",
        NormalizationEvent,
        ("ingestion_run_id", "observation_id", "field_name", "rule_id", "rule_version", "created_at"),
    ),
}


class BenchmarkRepository:
    """Local repository with idempotent upserts and non-destructive revisions."""

    def __init__(self, database_path="benchmark_bank/data/benchmark_bank.duckdb", read_only=False):
        self.database_path = str(database_path)
        if self.database_path != ":memory:" and not read_only:
            Path(self.database_path).parent.mkdir(parents=True, exist_ok=True)
        self.connection = duckdb.connect(self.database_path, read_only=read_only)
        if not read_only:
            self.apply_migrations()

    def close(self):
        self.connection.close()

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, traceback):
        self.close()

    def apply_migrations(self):
        self.connection.execute(
            """
            CREATE TABLE IF NOT EXISTS schema_migrations (
                version INTEGER PRIMARY KEY,
                description VARCHAR NOT NULL,
                applied_at TIMESTAMPTZ NOT NULL
            )
            """
        )
        applied = {
            row[0] for row in self.connection.execute(
                "SELECT version FROM schema_migrations"
            ).fetchall()
        }
        for version, description, sql in MIGRATIONS:
            if version in applied:
                continue
            self.connection.execute("BEGIN TRANSACTION")
            try:
                self.connection.execute(sql)
                self.connection.execute(
                    "INSERT INTO schema_migrations VALUES (?, ?, ?)",
                    [version, description, datetime.now(timezone.utc)],
                )
                self.connection.execute("COMMIT")
            except Exception:
                self.connection.execute("ROLLBACK")
                raise

    @staticmethod
    def _serialize(model: BaseModel):
        payload = model.model_dump(mode="json")
        text = json.dumps(
            payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"),
            allow_nan=False,
        )
        return payload, text, hashlib.sha256(text.encode("utf-8")).hexdigest()

    @staticmethod
    def _projection(config, model, payload):
        values = dict(payload)
        if config.name == "observation":
            raw = model.raw_value
            values["raw_value_numeric"] = (
                float(raw) if isinstance(raw, (int, float)) and not isinstance(raw, bool) else None
            )
            values["raw_value_text"] = str(raw) if raw is not None and values["raw_value_numeric"] is None else None
        return [values.get(field) for field in config.projected_fields]

    def _exists(self, config_name, entity_id):
        config = CONFIGS[config_name]
        return self.connection.execute(
            f"SELECT 1 FROM {config.table} WHERE {config.id_field} = ? AND is_current LIMIT 1",
            [entity_id],
        ).fetchone() is not None

    def _validate_database_references(self, config_name, model):
        if config_name == "ingestion_run" and not self._exists("source", model.source_id):
            raise ValueError(f"unknown source_id: {model.source_id}")
        if config_name == "observation":
            if not self._exists("source", model.source_id):
                raise ValueError(f"unknown source_id: {model.source_id}")
            if model.project_id and not self._exists("project", model.project_id):
                raise ValueError(f"unknown project_id: {model.project_id}")
            if not self._exists("ingestion_run", model.ingestion_run_id):
                raise ValueError(f"unknown ingestion_run_id: {model.ingestion_run_id}")
            for observation_id in model.input_observation_ids:
                if not self._exists("observation", observation_id):
                    raise ValueError(f"unknown input observation_id: {observation_id}")
        if config_name == "normalization_event":
            if not self._exists("ingestion_run", model.ingestion_run_id):
                raise ValueError(f"unknown ingestion_run_id: {model.ingestion_run_id}")
            if not self._exists("observation", model.observation_id):
                raise ValueError(f"unknown observation_id: {model.observation_id}")

    def _upsert(self, config_name, model, validate_references=True):
        config = CONFIGS[config_name]
        if not isinstance(model, config.model):
            model = config.model.model_validate(model)
        if validate_references:
            self._validate_database_references(config_name, model)
        payload, payload_text, content_hash = self._serialize(model)
        entity_id = getattr(model, config.id_field)
        existing = self.connection.execute(
            f"SELECT revision, content_hash FROM {config.table} "
            f"WHERE {config.id_field} = ? AND is_current",
            [entity_id],
        ).fetchone()
        if existing and existing[1] == content_hash:
            return UpsertResult(config.name, entity_id, existing[0], False)

        revision = (existing[0] + 1) if existing else 1
        if existing:
            self.connection.execute(
                f"UPDATE {config.table} SET is_current = false "
                f"WHERE {config.id_field} = ? AND is_current",
                [entity_id],
            )
        common_columns = [
            config.id_field, "revision", "is_current", "content_hash", "recorded_at"
        ]
        columns = common_columns + list(config.projected_fields) + ["payload_json"]
        values = [
            entity_id, revision, True, content_hash, datetime.now(timezone.utc),
            *self._projection(config, model, payload), payload_text,
        ]
        placeholders = ", ".join("?" for _ in columns)
        self.connection.execute(
            f"INSERT INTO {config.table} ({', '.join(columns)}) VALUES ({placeholders})",
            values,
        )
        return UpsertResult(config.name, entity_id, revision, True)

    def upsert_source(self, source):
        return self._upsert("source", source)

    def upsert_project(self, project):
        return self._upsert("project", project)

    def upsert_ingestion_run(self, run):
        return self._upsert("ingestion_run", run)

    def upsert_observation(self, observation):
        return self._upsert("observation", observation)

    def upsert_normalization_event(self, event):
        return self._upsert("normalization_event", event)

    def load_document(self, document):
        document = (
            document if isinstance(document, BenchmarkBankDocument)
            else BenchmarkBankDocument.model_validate(document)
        )
        results = []
        self.connection.execute("BEGIN TRANSACTION")
        try:
            for entity in document.sources:
                results.append(self._upsert("source", entity, validate_references=False))
            for entity in document.projects:
                results.append(self._upsert("project", entity, validate_references=False))
            for entity in document.ingestion_runs:
                results.append(self._upsert("ingestion_run", entity, validate_references=True))
            # Base observations precede derived observations so their inputs exist.
            observations = sorted(document.observations, key=lambda item: bool(item.input_observation_ids))
            for entity in observations:
                results.append(self._upsert("observation", entity, validate_references=True))
            for entity in document.normalization_events:
                results.append(self._upsert("normalization_event", entity, validate_references=True))
            self.connection.execute("COMMIT")
        except Exception:
            self.connection.execute("ROLLBACK")
            raise
        return results

    def _get(self, config_name, entity_id):
        config = CONFIGS[config_name]
        row = self.connection.execute(
            f"SELECT payload_json FROM {config.table} "
            f"WHERE {config.id_field} = ? AND is_current",
            [entity_id],
        ).fetchone()
        return config.model.model_validate(json.loads(row[0])) if row else None

    def get_source(self, source_id):
        return self._get("source", source_id)

    def get_project(self, project_id):
        return self._get("project", project_id)

    def get_ingestion_run(self, ingestion_run_id):
        return self._get("ingestion_run", ingestion_run_id)

    def get_observation(self, observation_id):
        return self._get("observation", observation_id)

    def get_normalization_event(self, event_id):
        return self._get("normalization_event", event_id)

    def history(self, config_name, entity_id):
        config = CONFIGS[config_name]
        rows = self.connection.execute(
            f"SELECT revision, is_current, content_hash, recorded_at, payload_json "
            f"FROM {config.table} WHERE {config.id_field} = ? ORDER BY revision",
            [entity_id],
        ).fetchall()
        return [
            Revision(row[0], row[1], row[2], row[3], config.model.model_validate(json.loads(row[4])))
            for row in rows
        ]

    def query_projects(self, technology=None, region=None, country_iso3=None):
        clauses, parameters = ["is_current"], []
        for field, value in (
            ("technology", technology), ("region", region), ("country_iso3", country_iso3)
        ):
            if value is not None:
                clauses.append(f"{field} = ?")
                parameters.append(value.upper() if field == "country_iso3" else value)
        rows = self.connection.execute(
            "SELECT payload_json FROM bank_projects WHERE " + " AND ".join(clauses)
            + " ORDER BY project_name",
            parameters,
        ).fetchall()
        return [Project.model_validate(json.loads(row[0])) for row in rows]

    def query_observations(
        self, metric=None, project_id=None, source_id=None, review_status=None,
        normalized_only=False,
    ):
        clauses, parameters = ["is_current"], []
        for field, value in (
            ("metric", metric), ("project_id", project_id), ("source_id", source_id),
            ("review_status", review_status),
        ):
            if value is not None:
                clauses.append(f"{field} = ?")
                parameters.append(value)
        if normalized_only:
            clauses.append("normalized_value IS NOT NULL OR normalized_low IS NOT NULL")
        rows = self.connection.execute(
            "SELECT payload_json FROM bank_observations WHERE " + " AND ".join(clauses)
            + " ORDER BY metric, observation_id",
            parameters,
        ).fetchall()
        return [Observation.model_validate(json.loads(row[0])) for row in rows]

    def counts(self):
        return {
            name: self.connection.execute(
                f"SELECT count(*) FROM {config.table} WHERE is_current"
            ).fetchone()[0]
            for name, config in CONFIGS.items()
        }
