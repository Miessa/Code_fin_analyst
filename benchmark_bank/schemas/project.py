"""Stable project identity independent of individual metric observations."""

from __future__ import annotations

from pydantic import Field, field_validator, model_validator

from .common import CanonicalModel, Identifier, ReviewStatus


class Project(CanonicalModel):
    schema_version: str = "1.0.0"
    project_id: Identifier
    project_name: str = Field(min_length=2, max_length=300)
    aliases: list[str] = Field(default_factory=list)
    country_name: str | None = Field(default=None, max_length=120)
    country_iso3: str | None = None
    region: str | None = Field(default=None, max_length=120)
    subregion: str | None = Field(default=None, max_length=120)
    technology: str | None = Field(default=None, max_length=80)
    project_type: str | None = Field(default=None, max_length=160)
    revenue_model: str | None = Field(default=None, max_length=160)
    latitude: float | None = Field(default=None, ge=-90, le=90)
    longitude: float | None = Field(default=None, ge=-180, le=180)
    identity_status: ReviewStatus = ReviewStatus.UNREVIEWED
    merged_into_project_id: Identifier | None = None
    metadata: dict = Field(default_factory=dict)

    @field_validator("country_iso3")
    @classmethod
    def normalize_iso3(cls, value):
        if value is None:
            return None
        value = value.upper()
        if len(value) != 3 or not value.isalpha():
            raise ValueError("country_iso3 must contain three letters")
        return value

    @field_validator("aliases")
    @classmethod
    def unique_aliases(cls, values):
        result = []
        seen = set()
        for value in values:
            key = value.casefold().strip()
            if key and key not in seen:
                seen.add(key)
                result.append(value.strip())
        return result

    @model_validator(mode="after")
    def valid_merge_target(self):
        if self.merged_into_project_id == self.project_id:
            raise ValueError("a project cannot be merged into itself")
        if self.identity_status == ReviewStatus.SUPERSEDED and not self.merged_into_project_id:
            raise ValueError("a superseded project requires merged_into_project_id")
        return self
