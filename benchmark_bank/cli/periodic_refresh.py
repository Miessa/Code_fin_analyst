"""Discover official source updates and rebuild staging without promotion."""

import argparse

from benchmark_bank.periodic_refresh import PeriodicRefreshOrchestrator


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--raw-dir", default="benchmark_bank/data/raw")
    parser.add_argument("--staging", default="benchmark_bank/data/staging.duckdb")
    parser.add_argument("--active", default="benchmark_bank/data/benchmark_bank.duckdb")
    parser.add_argument("--output-dir", default="benchmark_bank/outputs/periodic_refresh")
    parser.add_argument("--timeout", type=int, default=120)
    args = parser.parse_args(argv)
    report = PeriodicRefreshOrchestrator(raw_dir=args.raw_dir, staging_path=args.staging,
        active_path=args.active, output_dir=args.output_dir, timeout=args.timeout).run()
    print(f"Status: {report['status']}")
    print(f"Promotion performed: {report['promotion_performed']}")
    print(f"Report: {args.output_dir}/periodic_refresh_report.json")
    if report["status"] not in {"staging_ready", "no_change"}: raise SystemExit(1)


if __name__ == "__main__": main()
