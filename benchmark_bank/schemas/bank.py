"""Aggregate exchange document with referential-integrity validation."""

from __future__ import annotations

from collections import Counter

from pydantic import Field, model_validator

from .common import CanonicalModel
from .ingestion import IngestionRun, NormalizationEvent
from .observation import Observation
from .project import Project
from .source import Source


class BenchmarkBankDocument(CanonicalModel):
    schema_version: str = "1.0.0"
    sources: list[Source] = Field(default_factory=list)
    projects: list[Project] = Field(default_factory=list)
    ingestion_runs: list[IngestionRun] = Field(default_factory=list)
    observations: list[Observation] = Field(default_factory=list)
    normalization_events: list[NormalizationEvent] = Field(default_factory=list)

    @model_validator(mode="after")
    def references_exist_and_ids_are_unique(self):
        def index(items, attribute, label):
            values = [getattr(item, attribute) for item in items]
            duplicates = sorted(value for value, count in Counter(values).items() if count > 1)
            if duplicates:
                raise ValueError(f"duplicate {label} identifiers: {duplicates}")
            return set(values)

        source_ids = index(self.sources, "source_id", "source")
        project_ids = index(self.projects, "project_id", "project")
        run_ids = index(self.ingestion_runs, "ingestion_run_id", "ingestion run")
        observation_ids = index(self.observations, "observation_id", "observation")
        index(self.normalization_events, "normalization_event_id", "normalization event")

        for run in self.ingestion_runs:
            if run.source_id not in source_ids:
                raise ValueError(f"ingestion run {run.ingestion_run_id} references unknown source")
        for observation in self.observations:
            if observation.source_id not in source_ids:
                raise ValueError(f"observation {observation.observation_id} references unknown source")
            if observation.project_id and observation.project_id not in project_ids:
                raise ValueError(f"observation {observation.observation_id} references unknown project")
            if observation.ingestion_run_id not in run_ids:
                raise ValueError(f"observation {observation.observation_id} references unknown ingestion run")
            missing_inputs = set(observation.input_observation_ids) - observation_ids
            if missing_inputs:
                raise ValueError(
                    f"observation {observation.observation_id} has unknown derivation inputs: "
                    f"{sorted(missing_inputs)}"
                )
        for event in self.normalization_events:
            if event.ingestion_run_id not in run_ids:
                raise ValueError(f"normalization event {event.normalization_event_id} references unknown run")
            if event.observation_id not in observation_ids:
                raise ValueError(f"normalization event {event.normalization_event_id} references unknown observation")
        return self
