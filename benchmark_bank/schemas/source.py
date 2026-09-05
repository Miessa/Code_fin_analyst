"""Source and publication provenance."""

from __future__ import annotations

from datetime import date

from pydantic import Field, field_validator

from .common import CanonicalModel, Identifier, ReviewStatus, validate_checksum


class Source(CanonicalModel):
    schema_version: str = "1.0.0"
    source_id: Identifier
    organization: str = Field(min_length=2, max_length=200)
    title: str = Field(min_length=2, max_length=500)
    source_type: str = Field(min_length=2, max_length=80)
    publication_date: date | None = None
    data_period_start: date | None = None
    data_period_end: date | None = None
    canonical_url: str | None = Field(default=None, max_length=2000)
    license_name: str | None = Field(default=None, max_length=200)
    license_url: str | None = Field(default=None, max_length=2000)
    publisher_record_id: str | None = Field(default=None, max_length=250)
    content_checksum_sha256: str | None = None
    review_status: ReviewStatus = ReviewStatus.UNREVIEWED
    notes: str | None = Field(default=None, max_length=4000)
    metadata: dict = Field(default_factory=dict)

    @field_validator("content_checksum_sha256")
    @classmethod
    def checksum_is_sha256(cls, value):
        return validate_checksum(value)

    @field_validator("data_period_end")
    @classmethod
    def period_is_ordered(cls, value, info):
        start = info.data.get("data_period_start")
        if value is not None and start is not None and value < start:
            raise ValueError("data_period_end cannot precede data_period_start")
        return value
