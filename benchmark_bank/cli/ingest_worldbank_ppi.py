"""Ingest the official World Bank PPI STATA dataset into the local bank."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from benchmark_bank.sources import WorldBankPPIAdapter
from benchmark_bank.storage import BenchmarkRepository


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("input", help="Official World Bank PPI .dta file")
    parser.add_argument("--database", default="benchmark_bank/data/benchmark_bank.duckdb")
    parser.add_argument("--recent-from", type=int, default=2020)
    parser.add_argument(
        "--report", default="benchmark_bank/outputs/worldbank_ppi_ingestion_report.json"
    )
    args = parser.parse_args(argv)

    adapter = WorldBankPPIAdapter(args.input, recent_from_year=args.recent_from)
    document, report = adapter.build()
    with BenchmarkRepository(args.database) as repository:
        results = repository.load_document(document)
        changed = sum(result.changed for result in results)
        counts = repository.counts()

    report_path = Path(args.report)
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(
        json.dumps(report.model_dump(mode="json"), ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    print(f"Energy projects: {report.unique_energy_projects}")
    print(f"Default recent eligible cohort: {report.default_eligible_projects}")
    print(f"Older fallback projects: {report.older_fallback_projects}")
    print(f"Current database records: {counts}")
    print(f"Changed records this run: {changed}")
    print(f"Quality report: {report_path}")


if __name__ == "__main__":
    main()
