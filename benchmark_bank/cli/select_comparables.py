"""Build the analyzed-project profile and review comparable projects."""

from __future__ import annotations

import argparse
from arsel_core.orchestration import create_comparable_selection


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("registry", help="Phase 1 hypotheses_validees.json")
    parser.add_argument("--context", default="phase2/phase2_context.json")
    parser.add_argument("--database", default="benchmark_bank/data/benchmark_bank.duckdb")
    parser.add_argument("--output", default="outputs/phase2/comparable_selection.json")
    parser.add_argument("--candidates", type=int, default=10)
    parser.add_argument("--target", type=int, default=5)
    parser.add_argument("--minimum", type=int, default=3)
    parser.add_argument("--recent-only", action="store_true")
    args = parser.parse_args(argv)
    if not 1 <= args.minimum <= args.target <= args.candidates:
        parser.error("expected 1 <= minimum <= target <= candidates")

    payload = create_comparable_selection(
        args.registry, args.context, args.database, args.output,
        candidates=args.candidates, target=args.target, minimum=args.minimum,
        recent_only=args.recent_only,
    )
    print(f"\nComparables approuvés : {payload['approved_count']}")
    print(f"Statut : {payload['selection_status']}")
    print(f"Sélection : {args.output}")


if __name__ == "__main__":
    main()
