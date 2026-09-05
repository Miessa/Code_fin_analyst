"""Explainable comparable-project ranking."""

from __future__ import annotations

import math
from dataclasses import asdict, dataclass, field

from .features import ProjectFeatures


@dataclass(frozen=True)
class ProjectProfile:
    technology: str
    hydropower_configuration: str | None = None
    region: str | None = None
    country_iso3: str | None = None
    capacity_mw: float | None = None
    financial_close_year: int | None = None
    contract_period_years: float | None = None
    debt_share: float | None = None


@dataclass
class ComparableCandidate:
    project_id: str
    project_name: str
    score: float
    tier: str
    reasons: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    features: ProjectFeatures | None = None

    def to_dict(self):
        result = asdict(self)
        return result


def _similarity_ratio(a, b):
    if not a or not b or a <= 0 or b <= 0:
        return None
    return math.exp(-abs(math.log(a / b)))


def rank_comparables(
    profile: ProjectProfile,
    features: list[ProjectFeatures],
    *,
    metric: str = "investment_per_mw_usd",
    limit: int = 10,
    allow_historical_fallback: bool = True,
    minimum_capacity_ratio: float = 0.20,
    maximum_capacity_ratio: float = 5.0,
) -> list[ComparableCandidate]:
    """Rank same-technology projects with explicit weighted criteria."""
    ranked = []
    for item in features:
        if item.technology != profile.technology:
            continue
        if (
            profile.technology == "hydropower"
            and profile.hydropower_configuration
            and item.hydropower_configuration != profile.hydropower_configuration
        ):
            continue
        if getattr(item, metric, None) is None:
            continue
        if not item.default_eligible and not allow_historical_fallback:
            continue
        if profile.capacity_mw and item.capacity_mw:
            capacity_ratio = item.capacity_mw / profile.capacity_mw
            if not minimum_capacity_ratio <= capacity_ratio <= maximum_capacity_ratio:
                continue

        score, weight = 0.0, 0.0
        reasons = ["same technology"]
        warnings = []

        # Technology is a hard filter and contributes 35% of the score.
        score += 0.35
        weight += 0.35
        if profile.region and item.region:
            weight += 0.20
            if item.region == profile.region:
                score += 0.20
                reasons.append("same region")
            else:
                warnings.append("different region")
        capacity_similarity = _similarity_ratio(profile.capacity_mw, item.capacity_mw)
        if capacity_similarity is not None:
            weight += 0.25
            score += 0.25 * capacity_similarity
            reasons.append(f"capacity similarity {capacity_similarity:.0%}")
        if profile.financial_close_year and item.financial_close_year:
            weight += 0.15
            gap = abs(profile.financial_close_year - item.financial_close_year)
            year_similarity = max(0.0, 1 - gap / 10)
            score += 0.15 * year_similarity
            reasons.append(f"financial-close gap {gap} year(s)")
        if profile.contract_period_years and item.contract_period_years:
            similarity = _similarity_ratio(
                profile.contract_period_years, item.contract_period_years
            )
            weight += 0.05
            score += 0.05 * similarity
            reasons.append(f"contract-period similarity {similarity:.0%}")
        normalized = score / weight if weight else 0.0
        normalized *= 0.85 + 0.15 * item.quality_score
        if not item.default_eligible:
            normalized *= 0.75
            warnings.append("historical or non-active fallback")
        tier = "strong" if normalized >= 0.80 else "moderate" if normalized >= 0.65 else "weak"
        ranked.append(ComparableCandidate(
            project_id=item.project_id, project_name=item.project_name,
            score=round(normalized, 4), tier=tier, reasons=reasons,
            warnings=warnings, features=item,
        ))
    return sorted(ranked, key=lambda x: (-x.score, x.project_name))[:limit]
