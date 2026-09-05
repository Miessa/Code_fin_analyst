"""End-to-end Phase 2 orchestration."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

from .benchmark_engine import comparer
from .derived_metrics import calculer_indicateurs
from .professional_analysis import construire_analyse, generer_markdown
from .registry_normalization import normaliser_registre
from .detailed_benchmark import construire_tableau
from .word_report import generer_word
from .peer_benchmark import (
    enrich_benchmark_table, enrich_professional_analysis, load_peer_selection, position_project,
)
from .sector_benchmark import enrich_sector_table, load_irena_sector_benchmark, position_against_irena


PACKAGE_DIR = Path(__file__).resolve().parent
DEFAULT_REFERENCE = PACKAGE_DIR / "data" / "comparison_controls.json"
DETAILED_REFERENCE = PACKAGE_DIR.parent / "benchmark_hybrid" / "data" / "referentiel_normes.json"


def _load_json(path):
    with Path(path).open(encoding="utf-8") as stream:
        return json.load(stream)


def _validate_registry(registry):
    if not isinstance(registry, list):
        raise ValueError("Le registre Phase 1 doit être une liste JSON.")
    duplicates = []
    seen = set()
    for item in registry:
        if not isinstance(item, dict) or not item.get("cle"):
            raise ValueError("Chaque métrique doit être un objet avec une clé 'cle'.")
        if item["cle"] in seen:
            duplicates.append(item["cle"])
        seen.add(item["cle"])
    if duplicates:
        raise ValueError(f"Clés dupliquées dans le registre: {sorted(set(duplicates))}")


def executer_phase2(registre_path, reference_path=DEFAULT_REFERENCE, output_dir="outputs/phase2", contexte=None,
                    comparable_selection_path=None,
                    benchmark_database="benchmark_bank/data/benchmark_bank.duckdb"):
    registre = _load_json(registre_path)
    _validate_registry(registre)
    referentiel = _load_json(reference_path)
    registre_normalise, alertes_normalisation = normaliser_registre(registre, contexte)
    indicateurs = calculer_indicateurs(registre_normalise, contexte=contexte)
    comparaisons = comparer(indicateurs, referentiel, contexte=contexte)
    analyse = construire_analyse(registre_normalise, indicateurs, comparaisons)
    selection_path = Path(comparable_selection_path) if comparable_selection_path else Path(output_dir) / "comparable_selection.json"
    selection = load_peer_selection(selection_path)
    peer_result = position_project(selection, registre_normalise, indicateurs)
    sector = load_irena_sector_benchmark(
        benchmark_database, (contexte or {}).get("technology"), (contexte or {}).get("geography")
    ) if (contexte or {}).get("technology") else {
        "status":"NOT_PERFORMED", "reason":"technology absent from Phase 2 context", "references":[]}
    sector_result = position_against_irena(sector, registre_normalise, indicateurs, contexte)
    if DETAILED_REFERENCE.exists():
        referentiel_detaille = _load_json(DETAILED_REFERENCE)
        analyse["tableau_benchmark_detaille"] = construire_tableau(
            registre_normalise, indicateurs, referentiel_detaille, contexte
        )
    else:
        analyse["tableau_benchmark_detaille"] = []
    analyse["tableau_benchmark_detaille"] = enrich_benchmark_table(
        analyse["tableau_benchmark_detaille"], peer_result
    )
    analyse["tableau_benchmark_detaille"] = enrich_sector_table(
        analyse["tableau_benchmark_detaille"], sector_result
    )
    analyse = enrich_professional_analysis(analyse, peer_result)
    analyse["comparaison_projets_pairs"] = peer_result
    analyse["comparaison_sectorielle_irena"] = sector_result
    resultat = {
        "metadata": {
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "phase1_registry": str(Path(registre_path).resolve()),
            "benchmark_reference": str(Path(reference_path).resolve()),
            "benchmark_version": referentiel.get("_version"),
            "context": contexte or {},
            "comparable_selection": str(selection_path.resolve()) if selection else None,
            "benchmark_database": str(Path(benchmark_database).resolve()),
        },
        "registre_normalise": registre_normalise,
        "alertes_normalisation": alertes_normalisation,
        **analyse,
    }
    output = Path(output_dir)
    output.mkdir(parents=True, exist_ok=True)
    json_path = output / "analyse_financiere_phase2.json"
    md_path = output / "analyse_financiere_phase2.md"
    docx_path = output / "analyse_financiere_phase2.docx"
    resultat["metadata"]["word_output"] = str(docx_path.resolve())
    json_path.write_text(json.dumps(resultat, ensure_ascii=False, indent=2), encoding="utf-8")
    md_path.write_text(generer_markdown(resultat), encoding="utf-8")
    generer_word(resultat, docx_path)
    return resultat, json_path, md_path
