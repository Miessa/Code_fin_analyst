"""Adapter for the official World Bank PPI STATA project dataset."""

from __future__ import annotations

import hashlib
import json
import math
from collections import Counter
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any

import pandas as pd
from pydantic import Field

from benchmark_bank.schemas import (
    BenchmarkBankDocument, IngestionRun, NormalizationEvent, Observation, Project, Source,
)
from benchmark_bank.schemas.common import CanonicalModel


SOURCE_ID = "worldbank_ppi"
SOURCE_URL = "https://www.worldbank.org/content/dam/PPI/documents/2024-PPI-Full-DTA.dta"
DATA_PAGE_URL = "https://ppi.worldbank.org/en/ppidata"

REQUIRED_COLUMNS = {
    "ID", "name", "sector", "country", "Region", "FCY", "type", "stype",
    "status_n", "period", "private", "fees", "physical", "investment",
    "capacity", "pcapacity", "technol", "PRS", "OSR", "FundingYear",
    "debt", "equity",
}

REGION_MAP = {
    "AFR": "Sub-Saharan Africa",
    "EAP": "East Asia and Pacific",
    "ECA": "Europe and Central Asia",
    "LAC": "Latin America and Caribbean",
    "MENA": "Middle East and North Africa",
    "SAR": "South Asia",
}

TECHNOLOGY_MAP = {
    "Biogas": "biogas",
    "Biomass": "biomass",
    "Coal": "coal",
    "Diesel": "diesel",
    "Enhanced Geothermal": "geothermal",
    "Large Hydro (>50MW)": "hydropower",
    "Small Hydro (<50MW)": "hydropower",
    "Natural Gas": "natural_gas",
    "Natural Gas, Diesel": "natural_gas_diesel",
    "Nuclear": "nuclear",
    "Solar CSP": "solar_csp",
    "Solar PV": "solar_pv",
    "Waste": "waste_to_energy",
    "Wind, onshore": "onshore_wind",
    "Wind, offshore": "offshore_wind",
    "Wave": "wave",
    "Hydrogen": "hydrogen",
    "Steam": "steam",
    "Batteries": "battery_storage",
}

INELIGIBLE_DEFAULT_STATUSES = {"Cancelled", "Distressed", "Concluded"}


class PPIIngestionReport(CanonicalModel):
    source_id: str = SOURCE_ID
    artifact_path: str
    artifact_checksum_sha256: str
    rows_read: int
    energy_rows: int
    non_energy_rows_excluded: int
    unique_energy_projects: int
    repeated_energy_rows: int
    unclassified_projects_excluded: int = 0
    unclassified_rows_excluded: int = 0
    recent_projects: int
    default_eligible_projects: int
    older_fallback_projects: int
    project_status_counts: dict[str, int] = Field(default_factory=dict)
    technology_counts: dict[str, int] = Field(default_factory=dict)
    observation_counts: dict[str, int] = Field(default_factory=dict)
    normalization_event_count: int = 0
    missingness: dict[str, int] = Field(default_factory=dict)
    warnings: list[str] = Field(default_factory=list)


def _sha256(path):
    digest = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _present(value):
    if value is None:
        return False
    if isinstance(value, float) and math.isnan(value):
        return False
    return str(value).strip() not in {"", ".", "nan", "NaN", "NA", "N/A"}


def _text(value):
    return str(value).strip() if _present(value) else None


def _number(value):
    if not _present(value):
        return None
    try:
        number = float(str(value).replace(",", "").strip())
    except (TypeError, ValueError):
        return None
    return number if math.isfinite(number) else None


def _integer(value):
    number = _number(value)
    return int(number) if number is not None and number.is_integer() else None


def _safe_id(value):
    return str(_integer(value) if _integer(value) is not None else value).strip()


def _signature(parts):
    text = json.dumps(parts, ensure_ascii=False, sort_keys=True, default=str)
    return hashlib.sha256(text.encode("utf-8")).hexdigest()[:16]


def _first(rows, column):
    for value in rows[column]:
        if _present(value):
            return value
    return None


def _unique_text(rows, column):
    return sorted({_text(value) for value in rows[column] if _text(value)})


class WorldBankPPIAdapter:
    adapter_name = "worldbank_ppi"
    adapter_version = "1.0.0"

    def __init__(self, artifact_path, recent_from_year=2020):
        self.artifact_path = Path(artifact_path)
        self.recent_from_year = int(recent_from_year)

    def read(self):
        return pd.read_stata(self.artifact_path, convert_categoricals=True)

    def build(self):
        frame = self.read()
        return self.build_from_dataframe(frame, checksum=_sha256(self.artifact_path))

    def build_from_dataframe(self, frame, checksum="0" * 64):
        missing = sorted(REQUIRED_COLUMNS - set(frame.columns))
        if missing:
            raise ValueError(f"World Bank PPI columns missing: {missing}")

        rows_read = len(frame)
        energy_mask = frame["sector"].astype(str).str.strip().eq("Energy")
        energy = frame.loc[energy_mask].copy()
        energy["__source_row__"] = energy.index.astype(int) + 2
        closure_years = [value for value in (_integer(x) for x in frame["FCY"]) if value]
        data_start_year = min(closure_years) if closure_years else 1990
        data_end_year = max(closure_years) if closure_years else 2024
        run_id = f"worldbank_ppi:{data_end_year}:{checksum[:16]}"

        source = Source(
            source_id=SOURCE_ID,
            organization="World Bank",
            title=f"Private Participation in Infrastructure Database — through {data_end_year}",
            source_type="structured_project_dataset",
            data_period_start=date(data_start_year, 1, 1),
            data_period_end=date(data_end_year, 12, 31),
            canonical_url=DATA_PAGE_URL,
            publisher_record_id="WB_PPI",
            content_checksum_sha256=checksum,
            review_status="pending",
            notes=(
                "Investment fields are PPI investment commitments in current USD, "
                "not verified executed construction expenditure."
            ),
        )

        projects, observations, normalization_events, warnings = [], [], [], []
        observation_keys = set()
        observation_counts = Counter()
        technology_counts = Counter()
        status_counts = Counter()
        recent_count = eligible_count = fallback_count = 0
        unclassified_projects_excluded = unclassified_rows_excluded = 0
        classified_rows = 0

        for raw_project_id, rows in energy.groupby("ID", sort=True, dropna=False):
            if not _present(raw_project_id):
                warnings.append("energy row without World Bank project ID was skipped")
                continue
            wb_id = _safe_id(raw_project_id)
            project_id = f"worldbank_ppi:{wb_id}"
            project_name = _text(_first(rows, "name")) or f"World Bank PPI project {wb_id}"
            countries = _unique_text(rows, "country")
            regions_raw = _unique_text(rows, "Region")
            technologies_raw = [x for x in _unique_text(rows, "technol") if x != "NA"]
            technologies = sorted({TECHNOLOGY_MAP.get(value, value.lower().replace(" ", "_")) for value in technologies_raw})
            technology = technologies[0] if len(technologies) == 1 else ("mixed_energy" if technologies else None)
            if technology is None:
                unclassified_projects_excluded += 1
                unclassified_rows_excluded += len(rows)
                continue
            classified_rows += len(rows)
            fcy_values = sorted({value for value in (_integer(x) for x in rows["FCY"]) if value})
            financial_close_year = fcy_values[0] if len(fcy_values) == 1 else (max(fcy_values) if fcy_values else None)
            status_values = _unique_text(rows, "status_n")
            status = status_values[0] if len(status_values) == 1 else ("mixed" if status_values else None)
            recent = financial_close_year is not None and financial_close_year >= self.recent_from_year
            eligible = recent and status not in INELIGIBLE_DEFAULT_STATUSES
            recent_count += int(recent)
            eligible_count += int(eligible)
            fallback_count += int(not recent)
            technology_counts[technology or "unknown"] += 1
            status_counts[status or "unknown"] += 1

            ppi_types = _unique_text(rows, "type")
            subtypes = _unique_text(rows, "stype")
            revenue_sources = [x for x in _unique_text(rows, "PRS") if x not in {"N/A", "VGF"}]
            aliases = sorted({name for name in _unique_text(rows, "name") if name != project_name})
            projects.append(Project(
                project_id=project_id,
                project_name=project_name,
                aliases=aliases,
                country_name=countries[0] if len(countries) == 1 else None,
                region=REGION_MAP.get(regions_raw[0], regions_raw[0]) if len(regions_raw) == 1 else None,
                technology=technology,
                project_type=" / ".join(ppi_types + subtypes) or None,
                revenue_model=" / ".join(revenue_sources) or None,
                identity_status="pending",
                metadata={
                    "worldbank_project_id": wb_id,
                    "financial_close_year": financial_close_year,
                    "financial_close_years_reported": fcy_values,
                    "project_status": status,
                    "technologies": technologies,
                    "technologies_raw": technologies_raw,
                    "default_comparable_eligible": eligible,
                    "recent_cohort_from_year": self.recent_from_year,
                    "description": _text(_first(rows, "Description")),
                },
            ))

            def add(metric, raw_value, raw_unit, row_number, *, normalized_value=None,
                    normalized_unit=None, value_date=None, perimeter=None, statistic=None,
                    metadata=None):
                signature = (
                    project_id, metric, raw_value, raw_unit, value_date, perimeter,
                    json.dumps(metadata or {}, sort_keys=True, default=str),
                )
                if signature in observation_keys:
                    return None
                observation_keys.add(signature)
                observation_id = f"ppi:{wb_id}:{metric}:{_signature(signature)}"
                observations.append(Observation(
                    observation_id=observation_id,
                    source_id=SOURCE_ID,
                    project_id=project_id,
                    ingestion_run_id=run_id,
                    metric=metric,
                    observation_type="project",
                    value_status="reported",
                    raw_value=raw_value,
                    raw_unit=raw_unit,
                    normalized_value=normalized_value,
                    normalized_unit=normalized_unit,
                    currency="USD" if raw_unit and "USD" in raw_unit else None,
                    value_date=value_date,
                    statistic=statistic,
                    economic_perimeter=perimeter,
                    source_location=f"STATA row {int(row_number)}; World Bank PPI project ID {wb_id}",
                    quality_level="medium",
                    review_status="unreviewed",
                    metadata=metadata or {},
                ))
                observation_counts[metric] += 1
                if normalized_value is not None:
                    if raw_unit == "current USD million":
                        rule_id, formula = "rule:usd_million_to_usd", "raw_value * 1_000_000"
                    elif raw_unit == "percent" and normalized_unit == "ratio":
                        rule_id, formula = "rule:percent_to_ratio", "raw_value / 100"
                    else:
                        rule_id, formula = "rule:canonical_identity", "raw_value"
                    normalization_events.append(NormalizationEvent(
                        normalization_event_id=f"norm:{observation_id}",
                        ingestion_run_id=run_id,
                        observation_id=observation_id,
                        field_name="normalized_value",
                        rule_id=rule_id,
                        rule_version="1.0.0",
                        input_value=raw_value,
                        output_value=normalized_value,
                        formula=formula,
                        parameters={"raw_unit": raw_unit, "normalized_unit": normalized_unit},
                    ))
                return observation_id

            # Project-level facts are deduplicated across repeated PPI rows.
            for value in fcy_values:
                add("financial_close_year", value, "year", rows.iloc[0]["__source_row__"],
                    normalized_value=float(value), normalized_unit="year")
            for row_index, row in rows.iterrows():
                source_row = row["__source_row__"]
                investment_year = _integer(row.get("IY"))
                value_date = date(investment_year, 1, 1) if investment_year else None
                funding_year = _integer(row.get("FundingYear"))
                funding_date = date(funding_year, 1, 1) if funding_year else None

                for column, metric, perimeter in (
                    ("investment", "investment_commitment", "total PPI investment commitment; current USD"),
                    ("physical", "physical_asset_investment_commitment", "investment in physical assets; current USD"),
                    ("fees", "government_fee_commitment", "fees paid to government; current USD"),
                ):
                    value = _number(row.get(column))
                    if value is not None:
                        add(metric, value, "current USD million", source_row,
                            normalized_value=value * 1_000_000, normalized_unit="current USD",
                            value_date=value_date, perimeter=perimeter,
                            metadata={"investment_year": investment_year})

                capacity_value = _number(row.get("pcapacity"))
                capacity_unit = _text(row.get("capacity"))
                technology_raw = _text(row.get("technol"))
                if capacity_value is not None and capacity_unit:
                    normalized_capacity = capacity_value if capacity_unit == "MW" else None
                    add("planned_capacity", capacity_value, capacity_unit, source_row,
                        normalized_value=normalized_capacity,
                        normalized_unit="MW" if normalized_capacity is not None else None,
                        statistic="planned", metadata={"technology_raw": technology_raw})

                period = _number(row.get("period"))
                if period is not None:
                    add("contract_period", period, "year", source_row,
                        normalized_value=period, normalized_unit="year")

                private = _number(row.get("private"))
                if private is not None:
                    add("private_ownership_share", private, "percent", source_row,
                        normalized_value=private / 100.0, normalized_unit="ratio")

                debt = _number(row.get("debt"))
                if debt is not None:
                    add("debt_funding", debt, "current USD million", source_row,
                        normalized_value=debt * 1_000_000, normalized_unit="current USD",
                        value_date=funding_date, perimeter="reported debt funding")
                equity = _number(row.get("equity"))
                if equity is not None:
                    add("equity_funding", equity, "current USD million", source_row,
                        normalized_value=equity * 1_000_000, normalized_unit="current USD",
                        value_date=funding_date, perimeter="reported equity funding")

        run = IngestionRun(
            ingestion_run_id=run_id,
            source_id=SOURCE_ID,
            adapter_name=self.adapter_name,
            adapter_version=self.adapter_version,
            status="succeeded",
            started_at=datetime.now(timezone.utc),
            completed_at=datetime.now(timezone.utc),
            raw_artifact_path=str(self.artifact_path),
            raw_artifact_checksum_sha256=checksum,
            records_read=rows_read,
            records_accepted=classified_rows,
            records_rejected=rows_read - classified_rows,
            warning_count=len(warnings),
            configuration={
                "sector_filter": "Energy",
                "technology_filter": "classified projects only",
                "recent_from_year": self.recent_from_year,
                "default_ineligible_statuses": sorted(INELIGIBLE_DEFAULT_STATUSES),
            },
        )
        document = BenchmarkBankDocument(
            sources=[source], projects=projects, ingestion_runs=[run], observations=observations,
            normalization_events=normalization_events,
        )
        missingness = {
            column: int(energy[column].map(lambda value: not _present(value)).sum())
            for column in ("investment", "pcapacity", "period", "debt", "equity")
        }
        report = PPIIngestionReport(
            artifact_path=str(self.artifact_path),
            artifact_checksum_sha256=checksum,
            rows_read=rows_read,
            energy_rows=len(energy),
            non_energy_rows_excluded=rows_read - len(energy),
            unique_energy_projects=len(projects),
            repeated_energy_rows=classified_rows - len(projects),
            unclassified_projects_excluded=unclassified_projects_excluded,
            unclassified_rows_excluded=unclassified_rows_excluded,
            recent_projects=recent_count,
            default_eligible_projects=eligible_count,
            older_fallback_projects=fallback_count,
            project_status_counts=dict(status_counts),
            technology_counts=dict(technology_counts),
            observation_counts=dict(observation_counts),
            normalization_event_count=len(normalization_events),
            missingness=missingness,
            warnings=warnings,
        )
        return document, report
