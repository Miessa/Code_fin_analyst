"""Run Phase 2 from the validated registry produced by Étape 3."""

import argparse
import json
from pathlib import Path

from phase2.pipeline import DEFAULT_REFERENCE, executer_phase2


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("registry", nargs="?", default="hypotheses_validees.json")
    parser.add_argument("--references", default=str(DEFAULT_REFERENCE))
    parser.add_argument("--output-dir", default="outputs/phase2")
    parser.add_argument("--context", help="JSON file with technology/geography/currency/price_year")
    parser.add_argument("--comparable-selection", help="Analyst-approved comparable_selection.json")
    parser.add_argument("--benchmark-database", default="benchmark_bank/data/benchmark_bank.duckdb")
    args = parser.parse_args(argv)
    contexte = None
    context_path = args.context
    if context_path is None:
        for candidate in (Path("phase2_context.json"), Path("phase2/phase2_context.json")):
            if candidate.exists() and candidate.stat().st_size:
                context_path = str(candidate)
                break
    if context_path:
        with open(context_path, encoding="utf-8") as stream:
            contexte = json.load(stream)
    result, json_path, md_path = executer_phase2(
        args.registry, args.references, args.output_dir, contexte, args.comparable_selection,
        args.benchmark_database
    )
    compared = sum(x["status"] == "COMPARED" for x in result["comparaisons_benchmark"])
    print(f"Phase 2 terminée: {compared} comparaison(s) appliquée(s).")
    print(f"JSON: {json_path}")
    print(f"Markdown: {md_path}")
    print(f"Word: {Path(args.output_dir) / 'analyse_financiere_phase2.docx'}")


if __name__ == "__main__":
    main()
