"""Rank benchmark projects for a deterministic target-project profile."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from benchmark_bank.analytics import (
    ProjectProfile, build_project_features, calculate_benchmark_statistics,
    rank_comparables,
)
from benchmark_bank.storage import BenchmarkRepository


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("profile", help="JSON file containing the target ProjectProfile")
    parser.add_argument("--database", default="benchmark_bank/data/benchmark_bank.duckdb")
    parser.add_argument("--output", default="benchmark_bank/outputs/comparable_candidates.json")
    parser.add_argument("--limit", type=int, default=10)
    parser.add_argument("--metric", default="investment_per_mw_usd")
    parser.add_argument("--recent-only", action="store_true")
    args = parser.parse_args(argv)

    profile_data = json.loads(Path(args.profile).read_text(encoding="utf-8"))
    profile = ProjectProfile(**profile_data)
    with BenchmarkRepository(args.database, read_only=True) as repository:
        features = build_project_features(repository)
    candidates = rank_comparables(
        profile, features, metric=args.metric, limit=args.limit,
        allow_historical_fallback=not args.recent_only,
    )
    # These distributions are preliminary: Phase 2 must use analyst-approved IDs.
    statistics = calculate_benchmark_statistics(
        [candidate.features for candidate in candidates if candidate.features]
    )
    payload = {
        "schema_version": "1.0.0",
        "selection_status": "candidate_shortlist_not_analyst_approved",
        "profile": profile_data,
        "ranking_policy": {
            "hard_filter": "same technology, requested metric, capacity between 0.2x and 5x",
            "recent_only": args.recent_only,
            "metric": args.metric,
            "limit": args.limit,
        },
        "candidates": [candidate.to_dict() for candidate in candidates],
        "preliminary_statistics": [item.to_dict() for item in statistics],
    }
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Candidates: {len(candidates)}")
    print(f"Output: {output}")


if __name__ == "__main__":
    main()
