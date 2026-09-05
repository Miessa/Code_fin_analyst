"""Atomic source-backed metric observations."""

from __future__ import annotations

from datetime import date
from typing import Any

from pydantic import Field, field_validator, model_validator

from .common import (
    CanonicalModel,
    Identifier,
    MetricKey,
    ObservationType,
    QualityLevel,
    ReviewStatus,
    ValueStatus,
    validate_finite,
)


class Observation(CanonicalModel):
    schema_version: str = "1.0.0"
    observation_id: Identifier
    source_id: Identifier
    project_id: Identifier | None = None
    ingestion_run_id: Identifier
    metric: MetricKey
    observation_type: ObservationType = ObservationType.PROJECT
    value_status: ValueStatus = ValueStatus.REPORTED

    raw_value: float | str | None = None
    raw_low: float | None = None
    raw_high: float | None = None
    raw_unit: str | None = Field(default=None, max_length=160)

    normalized_value: float | None = None
    normalized_low: float | None = None
    normalized_high: float | None = None
    normalized_unit: str | None = Field(default=None, max_length=160)
    normalization_status: str = Field(default="not_normalized", max_length=50)

    currency: str | None = None
    price_year: int | None = Field(default=None, ge=1800, le=2200)
    value_date: date | None = None
    statistic: str | None = Field(default=None, max_length=100)
    scenario: str | None = Field(default=None, max_length=250)
    economic_perimeter: str | None = Field(default=None, max_length=500)
    estimate_stage: str | None = Field(default=None, max_length=100)
    includes_taxes: bool | None = None
    includes_financing_costs: bool | None = None
    source_location: str = Field(min_length=1, max_length=1000)
    source_excerpt: str | None = Field(default=None, max_length=4000)
    quality_level: QualityLevel = QualityLevel.UNKNOWN
    review_status: ReviewStatus = ReviewStatus.UNREVIEWED
    derivation_formula: str | None = Field(default=None, max_length=1000)
    input_observation_ids: list[Identifier] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)

    @field_validator(
        "raw_low", "raw_high", "normalized_value", "normalized_low", "normalized_high"
    )
    @classmethod
    def numbers_are_finite(cls, value):
        return validate_finite(value)

    @field_validator("raw_value")
    @classmethod
    def raw_number_is_finite(cls, value):
        return validate_finite(value) if isinstance(value, float) else value

    @field_validator("currency")
    @classmethod
    def normalize_currency(cls, value):
        if value is None:
            return None
        value = value.upper()
        if len(value) != 3 or not value.isalpha():
            raise ValueError("currency must be a three-letter ISO-style code")
        return value

    @model_validator(mode="after")
    def coherent_values(self):
        raw_present = any(x is not None for x in (self.raw_value, self.raw_low, self.raw_high))
        normalized_present = any(
            x is not None
            for x in (self.normalized_value, self.normalized_low, self.normalized_high)
        )
        if not raw_present and not normalized_present:
            raise ValueError("an observation requires a raw or normalized value")
        if (self.raw_low is None) != (self.raw_high is None):
            raise ValueError("raw ranges require both raw_low and raw_high")
        if self.raw_low is not None and self.raw_low > self.raw_high:
            raise ValueError("raw_low cannot exceed raw_high")
        if (self.normalized_low is None) != (self.normalized_high is None):
            raise ValueError("normalized ranges require both normalized_low and normalized_high")
        if self.normalized_low is not None and self.normalized_low > self.normalized_high:
            raise ValueError("normalized_low cannot exceed normalized_high")
        if normalized_present and not self.normalized_unit:
            raise ValueError("normalized values require normalized_unit")
        if self.value_status == ValueStatus.DERIVED:
            if not self.derivation_formula or not self.input_observation_ids:
                raise ValueError("derived observations require formula and input observations")
        elif self.input_observation_ids:
            raise ValueError("input observations are only valid for derived observations")
        return self
