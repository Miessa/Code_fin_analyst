"""Conservative project-level features derived from atomic observations."""

from __future__ import annotations

import json
from collections import defaultdict
from dataclasses import asdict, dataclass, field
from typing import Any


@dataclass(frozen=True)
class QualityIssue:
    code: str
    field: str
    message: str


@dataclass
class ProjectFeatures:
    project_id: str
    project_name: str
    country_iso3: str | None
    country_name: str | None
    region: str | None
    technology: str | None
    hydropower_configuration: str | None
    financial_close_year: int | None
    project_status: str | None
    default_eligible: bool
    investment_usd: float | None = None
    capacity_mw: float | None = None
    investment_per_mw_usd: float | None = None
    investment_per_kw_usd: float | None = None
    debt_usd: float | None = None
    equity_usd: float | None = None
    debt_share: float | None = None
    equity_share: float | None = None
    contract_period_years: float | None = None
    private_ownership_share: float | None = None
    quality_score: float = 0.0
    issues: list[QualityIssue] = field(default_factory=list)
    evidence_observation_ids: dict[str, list[str]] = field(default_factory=dict)

    def to_dict(self):
        return asdict(self)


def _unique_positive(observations, metric, issues, *, allow_zero=False):
    candidates = [
        item for item in observations
        if item["metric"] == metric and item["normalized_value"] is not None
        and (item["normalized_value"] >= 0 if allow_zero else item["normalized_value"] > 0)
    ]
    values = sorted({float(item["normalized_value"]) for item in candidates})
    ids = [item["observation_id"] for item in candidates]
    if not values:
        issues.append(QualityIssue("missing_or_nonpositive", metric, f"No usable {metric} value"))
        return None, ids
    if len(values) > 1:
        issues.append(QualityIssue(
            "ambiguous_multiple_values", metric,
            f"{len(values)} distinct values; no undocumented aggregation was applied",
        ))
        return None, ids
    return values[0], ids


def build_project_features(repository) -> list[ProjectFeatures]:
    """Build auditable features; ambiguous source values remain unavailable."""
    project_rows = repository.connection.execute(
        "SELECT payload_json FROM current_projects ORDER BY project_id"
    ).fetchall()
    observation_rows = repository.connection.execute(
        """SELECT project_id, observation_id, metric, normalized_value
           FROM current_observations WHERE project_id IS NOT NULL"""
    ).fetchall()
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for project_id, observation_id, metric, value in observation_rows:
        grouped[project_id].append({
            "observation_id": observation_id, "metric": metric, "normalized_value": value,
        })

    results = []
    for (payload_text,) in project_rows:
        project = json.loads(payload_text)
        metadata = project.get("metadata") or {}
        identity_text = " ".join([
            project.get("project_name") or "", metadata.get("description") or "",
        ]).casefold()
        hydro_configuration = None
        if project.get("technology") == "hydropower":
            hydro_configuration = (
                "pumped_storage" if "pumped storage" in identity_text
                or "pumped-storage" in identity_text else "conventional"
            )
        observations = grouped.get(project["project_id"], [])
        issues: list[QualityIssue] = []
        evidence = {}
        investment, evidence["investment_usd"] = _unique_positive(
            observations, "investment_commitment", issues
        )
        capacity, evidence["capacity_mw"] = _unique_positive(
            observations, "planned_capacity", issues
        )
        debt, evidence["debt_usd"] = _unique_positive(observations, "debt_funding", issues)
        equity, evidence["equity_usd"] = _unique_positive(observations, "equity_funding", issues)
        period, evidence["contract_period_years"] = _unique_positive(
            observations, "contract_period", issues
        )
        private, evidence["private_ownership_share"] = _unique_positive(
            observations, "private_ownership_share", issues
        )

        def plausible(value, field_name, low, high):
            if value is not None and not low <= value <= high:
                issues.append(QualityIssue(
                    "outside_plausibility_range", field_name,
                    f"{value:g} outside accepted analytical range [{low:g}, {high:g}]",
                ))
                return None
            return value

        capacity = plausible(capacity, "capacity_mw", 0.1, 20_000)
        period = plausible(period, "contract_period_years", 1, 100)
        private = plausible(private, "private_ownership_share", 0.000001, 1)

        investment_per_mw = investment / capacity if investment and capacity else None
        if investment_per_mw is not None:
            investment_per_kw = investment_per_mw / 1000
            if not 50 <= investment_per_kw <= 30_000:
                issues.append(QualityIssue(
                    "outside_plausibility_range", "investment_per_kw_usd",
                    f"{investment_per_kw:g} outside accepted analytical range [50, 30000]",
                ))
                investment_per_mw = None
        debt_share = debt / (debt + equity) if debt and equity and debt + equity > 0 else None
        status = metadata.get("project_status")
        default_eligible = bool(metadata.get("default_comparable_eligible"))
        if not default_eligible:
            issues.append(QualityIssue(
                "not_default_eligible", "project",
                "Outside recent active default cohort; available only for controlled fallback",
            ))
        core_available = sum(x is not None for x in (investment, capacity, period, debt_share))
        ambiguity_count = sum(i.code == "ambiguous_multiple_values" for i in issues)
        quality_score = max(0.0, min(1.0, 0.25 + 0.15 * core_available - 0.15 * ambiguity_count))
        results.append(ProjectFeatures(
            project_id=project["project_id"], project_name=project["project_name"],
            country_iso3=project.get("country_iso3"), country_name=project.get("country_name"),
            region=project.get("region"), technology=project.get("technology"),
            hydropower_configuration=hydro_configuration,
            financial_close_year=metadata.get("financial_close_year"), project_status=status,
            default_eligible=default_eligible, investment_usd=investment, capacity_mw=capacity,
            investment_per_mw_usd=investment_per_mw,
            investment_per_kw_usd=investment_per_mw / 1000 if investment_per_mw else None,
            debt_usd=debt, equity_usd=equity, debt_share=debt_share,
            equity_share=1 - debt_share if debt_share is not None else None,
            contract_period_years=period, private_ownership_share=private,
            quality_score=round(quality_score, 3), issues=issues, evidence_observation_ids=evidence,
        ))
    return results
