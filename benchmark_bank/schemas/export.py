"""Export canonical Pydantic contracts as JSON Schema files."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from . import BenchmarkBankDocument, IngestionRun, NormalizationEvent, Observation, Project, Source


MODELS = {
    "source": Source,
    "project": Project,
    "observation": Observation,
    "ingestion_run": IngestionRun,
    "normalization_event": NormalizationEvent,
    "benchmark_bank": BenchmarkBankDocument,
}


def export_json_schemas(output_dir):
    output = Path(output_dir)
    output.mkdir(parents=True, exist_ok=True)
    paths = []
    for name, model in MODELS.items():
        path = output / f"{name}.schema.json"
        path.write_text(
            json.dumps(model.model_json_schema(), ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        paths.append(path)
    return paths


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", default="benchmark_bank/schemas/json")
    args = parser.parse_args(argv)
    for path in export_json_schemas(args.output_dir):
        print(path)


if __name__ == "__main__":
    main()
