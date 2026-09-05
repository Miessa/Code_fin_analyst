"""Build an auditable JSON snapshot of normalized benchmark project features."""

from __future__ import annotations

import argparse
import json
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

from benchmark_bank.analytics import build_project_features
from benchmark_bank.storage import BenchmarkRepository


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--database", default="benchmark_bank/data/benchmark_bank.duckdb")
    parser.add_argument(
        "--output", default="benchmark_bank/outputs/project_features.json"
    )
    args = parser.parse_args(argv)
    with BenchmarkRepository(args.database, read_only=True) as repository:
        features = build_project_features(repository)
    payload = {
        "schema_version": "1.0.0",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "project_count": len(features),
        "default_eligible_count": sum(item.default_eligible for item in features),
        "metric_availability": {
            metric: sum(getattr(item, metric) is not None for item in features)
            for metric in (
                "investment_usd", "capacity_mw", "investment_per_mw_usd",
                "debt_share", "contract_period_years", "private_ownership_share",
            )
        },
        "quality_issue_counts": dict(Counter(
            issue.code for item in features for issue in item.issues
        )),
        "projects": [item.to_dict() for item in features],
    }
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Analytical projects: {len(features)}")
    print(f"Default eligible: {payload['default_eligible_count']}")
    print(f"Metric availability: {payload['metric_availability']}")
    print(f"Output: {output}")


if __name__ == "__main__":
    main()
