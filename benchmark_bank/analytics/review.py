"""Interactive, auditable analyst review of comparable candidates."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime, timezone

from .statistics import calculate_benchmark_statistics


@dataclass
class ComparableDecision:
    project_id: str
    project_name: str
    decision: str
    score: float
    comment: str | None = None


def review_candidates(candidates, *, target=5, minimum=3, input_fn=input, output_fn=print):
    """Review candidates; invalid commands never advance and `b` goes back."""
    decisions = []
    index = 0
    while index < len(candidates):
        candidate = candidates[index]
        f = candidate.features
        output_fn("\n" + "─" * 60)
        output_fn(f"Candidat {index + 1}/{len(candidates)} — {candidate.project_name}")
        output_fn(
            f"Pays: {(f.country_name if f else None) or 'inconnu'} | "
            f"Technologie: {(f.technology if f else None) or 'inconnue'} | "
            f"Puissance: {(f.capacity_mw if f else None) or 'inconnue'} MW"
        )
        output_fn(f"Score: {candidate.score:.1%} ({candidate.tier})")
        output_fn("Raisons: " + "; ".join(candidate.reasons))
        if candidate.warnings:
            output_fn("Avertissements: " + "; ".join(candidate.warnings))
        command = input_fn("[a] approuver  [r] rejeter  [s] passer  [i] inspecter  [b] retour  [q] terminer > ").strip().lower()
        if command == "i":
            output_fn(str(f.to_dict() if f else {}))
            continue
        if command == "b":
            if index == 0:
                output_fn("Aucun candidat précédent.")
            else:
                index -= 1
                if decisions and decisions[-1].project_id == candidates[index].project_id:
                    decisions.pop()
            continue
        if command == "q":
            break
        if command not in {"a", "r", "s"}:
            output_fn("Choix invalide : utilisez a, r, s, i, b ou q.")
            continue
        decision = {"a": "approved", "r": "rejected", "s": "skipped"}[command]
        comment = None
        if command == "r":
            comment = input_fn("Motif du rejet (facultatif) > ").strip() or None
        decisions.append(ComparableDecision(
            candidate.project_id, candidate.project_name, decision, candidate.score, comment
        ))
        index += 1
        if sum(item.decision == "approved" for item in decisions) >= target:
            break
    approved_ids = {item.project_id for item in decisions if item.decision == "approved"}
    approved_features = [c.features for c in candidates if c.project_id in approved_ids and c.features]
    return {
        "reviewed_at": datetime.now(timezone.utc).isoformat(),
        "selection_status": "analyst_approved" if len(approved_ids) >= minimum else "insufficient_approved_comparables",
        "minimum_desired": minimum,
        "target": target,
        "approved_count": len(approved_ids),
        "decisions": [asdict(item) for item in decisions],
        "approved_project_ids": sorted(approved_ids),
        "benchmark_statistics": [
            item.to_dict() for item in calculate_benchmark_statistics(approved_features)
        ],
    }
