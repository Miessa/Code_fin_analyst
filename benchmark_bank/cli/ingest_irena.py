"""Extract IRENA sector statistics into the staging benchmark bank."""

import argparse
import json
from pathlib import Path

from benchmark_bank.sources import IRENATabularAdapter
from benchmark_bank.storage import BenchmarkRepository


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("xlsx", help="Official IRENA Renewable Power Generation Costs Excel datafile")
    parser.add_argument("--database", default="benchmark_bank/data/staging.duckdb")
    parser.add_argument("--report", default="benchmark_bank/outputs/irena_tabular_ingestion_report.json")
    parser.add_argument("--observations", default="benchmark_bank/outputs/irena_sector_statistics.json")
    args = parser.parse_args(argv)
    document, report = IRENATabularAdapter(args.xlsx).build()
    with BenchmarkRepository(args.database) as repository:
        results = repository.load_document(document)
    report_path, observations_path = Path(args.report), Path(args.observations)
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(json.dumps(report.model_dump(mode="json"), ensure_ascii=False, indent=2), encoding="utf-8")
    observations_path.write_text(json.dumps({
        "schema_version": "1.0.0", "source_id": report.source_id,
        "observations": [item.model_dump(mode="json") for item in document.observations],
    }, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Sector statistics: {report.observation_count}")
    print(f"Changed database records: {sum(item.changed for item in results)}")
    print(f"Report: {report_path}")
    print(f"Observations: {observations_path}")


if __name__ == "__main__": main()
