"""Metric-specific distributions for approved comparable projects."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from statistics import mean

import numpy as np

from .features import ProjectFeatures


@dataclass(frozen=True)
class BenchmarkStatistic:
    metric: str
    unit: str
    sample_size: int
    minimum: float | None
    p25: float | None
    median: float | None
    mean: float | None
    p75: float | None
    maximum: float | None
    project_ids: list[str]

    def to_dict(self):
        return asdict(self)


METRIC_UNITS = {
    "investment_per_mw_usd": "USD/MW",
    "investment_per_kw_usd": "USD/kW",
    "debt_share": "ratio",
    "equity_share": "ratio",
    "contract_period_years": "year",
    "private_ownership_share": "ratio",
}


def calculate_benchmark_statistics(
    projects: list[ProjectFeatures], metrics: list[str] | None = None
) -> list[BenchmarkStatistic]:
    metrics = metrics or list(METRIC_UNITS)
    results = []
    for metric in metrics:
        pairs = [(p.project_id, getattr(p, metric, None)) for p in projects]
        pairs = [(project_id, float(value)) for project_id, value in pairs if value is not None]
        values = [value for _, value in pairs]
        results.append(BenchmarkStatistic(
            metric=metric, unit=METRIC_UNITS.get(metric, "unknown"), sample_size=len(values),
            minimum=min(values) if values else None,
            p25=float(np.percentile(values, 25)) if values else None,
            median=float(np.percentile(values, 50)) if values else None,
            mean=mean(values) if values else None,
            p75=float(np.percentile(values, 75)) if values else None,
            maximum=max(values) if values else None,
            project_ids=[project_id for project_id, _ in pairs],
        ))
    return results
