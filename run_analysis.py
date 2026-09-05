"""Resume ARSEL from an already validated Phase 1 registry."""

import argparse
from arsel_core.orchestration import orchestrate_validated_analysis


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("registry", nargs="?", default="hypotheses_validees.json")
    parser.add_argument("--context", default="phase2/phase2_context.json")
    parser.add_argument("--database", default="benchmark_bank/data/benchmark_bank.duckdb")
    parser.add_argument("--output-dir", default="outputs/phase2")
    parser.add_argument("--non-interactive", action="store_true")
    args = parser.parse_args(argv)
    orchestrate_validated_analysis(
        args.registry, context_path=args.context, database_path=args.database,
        output_dir=args.output_dir, interactive=not args.non_interactive,
    )


if __name__ == "__main__": main()
