"""Ingestion execution and normalization lineage records."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import Field, field_validator, model_validator

from .common import (
    CanonicalModel,
    Identifier,
    RunStatus,
    utc_now,
    validate_aware_datetime,
    validate_checksum,
)


class IngestionRun(CanonicalModel):
    schema_version: str = "1.0.0"
    ingestion_run_id: Identifier
    source_id: Identifier
    adapter_name: str = Field(min_length=2, max_length=120)
    adapter_version: str = Field(min_length=1, max_length=40)
    status: RunStatus = RunStatus.RUNNING
    started_at: datetime = Field(default_factory=utc_now)
    completed_at: datetime | None = None
    raw_artifact_path: str | None = Field(default=None, max_length=2000)
    raw_artifact_checksum_sha256: str | None = None
    records_read: int = Field(default=0, ge=0)
    records_accepted: int = Field(default=0, ge=0)
    records_rejected: int = Field(default=0, ge=0)
    warning_count: int = Field(default=0, ge=0)
    error_summary: str | None = Field(default=None, max_length=4000)
    configuration: dict[str, Any] = Field(default_factory=dict)

    @field_validator("started_at", "completed_at")
    @classmethod
    def timestamps_are_aware(cls, value):
        return validate_aware_datetime(value)

    @field_validator("raw_artifact_checksum_sha256")
    @classmethod
    def checksum_is_sha256(cls, value):
        return validate_checksum(value)

    @model_validator(mode="after")
    def coherent_status(self):
        if self.completed_at is not None and self.completed_at < self.started_at:
            raise ValueError("completed_at cannot precede started_at")
        if self.status == RunStatus.RUNNING and self.completed_at is not None:
            raise ValueError("a running ingestion cannot have completed_at")
        if self.status != RunStatus.RUNNING and self.completed_at is None:
            raise ValueError("a completed ingestion status requires completed_at")
        if self.records_accepted + self.records_rejected > self.records_read:
            raise ValueError("accepted plus rejected records cannot exceed records_read")
        return self


class NormalizationEvent(CanonicalModel):
    schema_version: str = "1.0.0"
    normalization_event_id: Identifier
    ingestion_run_id: Identifier
    observation_id: Identifier
    field_name: str = Field(min_length=1, max_length=120)
    rule_id: Identifier
    rule_version: str = Field(min_length=1, max_length=40)
    input_value: Any = None
    output_value: Any = None
    formula: str | None = Field(default=None, max_length=1000)
    parameters: dict[str, Any] = Field(default_factory=dict)
    warnings: list[str] = Field(default_factory=list)
    created_at: datetime = Field(default_factory=utc_now)

    @field_validator("created_at")
    @classmethod
    def timestamp_is_aware(cls, value):
        return validate_aware_datetime(value)
