"""Resumable orchestration from a validated registry to final Phase 2 reports."""

from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

from benchmark_bank.analytics import (
    build_project_features, load_project_profile, rank_comparables, review_candidates,
)
from benchmark_bank.storage import BenchmarkRepository
from phase2.pipeline import executer_phase2


DEFAULT_DB = Path("benchmark_bank/data/benchmark_bank.duckdb")
DEFAULT_OUTPUT = Path("outputs/phase2")


def sha256_file(path):
    path = Path(path)
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _artifact(path):
    path = Path(path)
    return {
        "path": str(path.resolve()), "exists": path.exists(),
        "sha256": sha256_file(path) if path.exists() and path.is_file() else None,
        "size_bytes": path.stat().st_size if path.exists() and path.is_file() else None,
    }


def _profile_signature(profile_dict):
    encoded = json.dumps(profile_dict, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()


def _selection_compatible(selection, built, registry_path, context_path, database_path):
    reasons = []
    expected = _profile_signature(built.to_dict()["profile"])
    provenance = selection.get("provenance") or {}
    if provenance.get("profile_sha256") != expected:
        reasons.append("profil du projet modifié")
    if provenance.get("registry_sha256") != sha256_file(registry_path):
        reasons.append("registre Phase 1 modifié")
    if context_path and Path(context_path).exists() and provenance.get("context_sha256") != sha256_file(context_path):
        reasons.append("contexte Phase 2 modifié")
    if Path(database_path).exists() and provenance.get("benchmark_database_sha256") != sha256_file(database_path):
        reasons.append("banque de benchmarks modifiée")
    return not reasons, reasons


def create_comparable_selection(registry_path, context_path, database_path, output_path,
                                *, candidates=10, target=5, minimum=3,
                                recent_only=False,
                                input_fn=input, output_fn=print):
    built = load_project_profile(registry_path, context_path)
    with BenchmarkRepository(database_path, read_only=True) as repository:
        features = build_project_features(repository)
    ranked = rank_comparables(
        built.profile, features, limit=candidates,
        allow_historical_fallback=not recent_only,
    )
    output_fn(f"\nProjet analysé : {built.project_name}")
    for warning in built.warnings: output_fn(f"ATTENTION : {warning}")
    selection = review_candidates(
        ranked, target=target, minimum=minimum, input_fn=input_fn, output_fn=output_fn
    )
    provenance = {
        "registry_sha256": sha256_file(registry_path),
        "context_sha256": sha256_file(context_path) if context_path and Path(context_path).exists() else None,
        "benchmark_database_sha256": sha256_file(database_path),
        "profile_sha256": _profile_signature(built.to_dict()["profile"]),
    }
    payload = {
        "schema_version": "1.1.0", "analyzed_project": built.to_dict(),
        "provenance": provenance,
        "ranking_policy": {"technology_hard_filter": True,
            "hydropower_configuration_hard_filter": True,
            "capacity_hard_filter": "0.2x to 5x analyzed-project capacity",
            "historical_fallback_allowed": not recent_only,
            "candidate_limit": candidates},
        **selection,
    }
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return payload


def orchestrate_validated_analysis(registry_path="hypotheses_validees.json", *,
                                  context_path="phase2/phase2_context.json",
                                  database_path=DEFAULT_DB, output_dir=DEFAULT_OUTPUT,
                                  source_model=None, interactive=True,
                                  input_fn=input, output_fn=print):
    """Resume at the validated registry, optionally review peers, then run Phase 2."""
    registry_path, context_path = Path(registry_path), Path(context_path)
    database_path, output_dir = Path(database_path), Path(output_dir)
    selection_path = output_dir / "comparable_selection.json"
    manifest_path = output_dir / "analysis_manifest.json"
    if not registry_path.exists(): raise FileNotFoundError(registry_path)
    context = json.loads(context_path.read_text(encoding="utf-8-sig")) if context_path.exists() else {}
    stages = {"phase1_registry": "reused", "comparable_selection": "not_run", "phase2": "pending"}

    selection = None
    built = load_project_profile(registry_path, context_path if context_path.exists() else None)
    if selection_path.exists():
        selection = json.loads(selection_path.read_text(encoding="utf-8-sig"))
        compatible, reasons = _selection_compatible(
            selection, built, registry_path, context_path if context_path.exists() else None, database_path
        )
        if not compatible:
            output_fn("Sélection existante obsolète : " + "; ".join(reasons))
        if interactive:
            while True:
                choice = input_fn("Sélection existante : [r] réutiliser  [m/n] refaire  [s] ignorer  [q] quitter > ").strip().lower()
                if choice == "r" and compatible:
                    stages["comparable_selection"] = "reused"; break
                if choice == "r":
                    output_fn("Réutilisation refusée : la sélection n'est plus compatible."); continue
                if choice in {"m", "n"}: selection = None; break
                if choice == "s": selection = None; stages["comparable_selection"] = "skipped"; break
                if choice == "q": return None
                output_fn("Choix invalide.")
        elif compatible:
            stages["comparable_selection"] = "reused"
        else:
            selection = None

    if selection is None and stages["comparable_selection"] != "skipped":
        if database_path.exists() and interactive:
            selection = create_comparable_selection(
                registry_path, context_path if context_path.exists() else None,
                database_path, selection_path, input_fn=input_fn, output_fn=output_fn
            )
            stages["comparable_selection"] = "completed"
        elif not database_path.exists():
            stages["comparable_selection"] = "unavailable_database"
        else:
            stages["comparable_selection"] = "not_run_non_interactive"

    result, json_path, md_path = executer_phase2(
        registry_path, output_dir=output_dir, contexte=context,
        comparable_selection_path=selection_path if selection is not None else output_dir / "__no_selection__.json",
        benchmark_database=database_path,
    )
    docx_path = output_dir / "analyse_financiere_phase2.docx"
    stages["phase2"] = "completed"
    manifest = {
        "schema_version": "1.0.0", "generated_at": datetime.now(timezone.utc).isoformat(),
        "status": "completed", "stages": stages,
        "inputs": {"source_model": _artifact(source_model) if source_model else None,
                   "phase1_registry": _artifact(registry_path),
                   "phase2_context": _artifact(context_path) if context_path.exists() else None,
                   "benchmark_database": _artifact(database_path) if database_path.exists() else None,
                   "comparable_selection": _artifact(selection_path) if selection is not None else None},
        "outputs": {"json": _artifact(json_path), "markdown": _artifact(md_path), "word": _artifact(docx_path)},
        "peer_benchmark_status": result.get("comparaison_projets_pairs", {}).get("status"),
    }
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    output_fn(f"Manifeste : {manifest_path}")
    return manifest
