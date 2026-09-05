"""Build and quality-check a staging benchmark bank; optionally promote it."""

import argparse

from benchmark_bank.governance import QualityPolicy, refresh_worldbank_bank


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("artifact", help="Official World Bank PPI .dta file")
    parser.add_argument("--staging", default="benchmark_bank/data/staging.duckdb")
    parser.add_argument("--active", default="benchmark_bank/data/benchmark_bank.duckdb")
    parser.add_argument("--output-dir", default="benchmark_bank/outputs/governance")
    parser.add_argument("--recent-from", type=int, default=2020)
    parser.add_argument("--irena-data", default="benchmark_bank/data/raw/irena_rpgc_2024.xlsx",
                        help="Official IRENA Excel datafile; omit with an empty value to disable")
    parser.add_argument("--promote", action="store_true",
                        help="Replace active bank only if every quality gate passes")
    args = parser.parse_args(argv)
    report = refresh_worldbank_bank(
        args.artifact, staging_path=args.staging, active_path=args.active,
        output_dir=args.output_dir, recent_from=args.recent_from,
        policy=QualityPolicy(minimum_sector_statistics=20), promote=args.promote,
        irena_artifact_path=args.irena_data or None,
    )
    print(f"Status: {report['status']}")
    print(f"Quality gates passed: {report['quality']['passed']}")
    print(f"Report: {args.output_dir}/update_report.json")


if __name__ == "__main__": main()
