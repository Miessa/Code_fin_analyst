"""Position the analyzed project against analyst-approved project peers."""

from __future__ import annotations

import json
from pathlib import Path


METRICS = {
    "investment_per_mw_usd": ("Coût total d'investissement par MW", "total_investment_per_mw"),
    "investment_per_kw_usd": ("Coût total d'investissement par kW", "total_investment_per_kw"),
    "debt_share": ("Part de dette", "debt_share"),
    "equity_share": ("Part de fonds propres", "equity_share"),
    "contract_period_years": ("Durée contractuelle", "contract_period_years"),
    "private_ownership_share": ("Participation privée", "private_ownership_share"),
}


def _position(value, stat):
    if value is None: return "PROJECT_VALUE_UNAVAILABLE"
    if not stat.get("sample_size"): return "NO_PEER_DATA"
    if value < stat["minimum"]: return "BELOW_MIN"
    if value < stat["p25"]: return "BELOW_P25"
    if value <= stat["p75"]: return "P25_P75"
    if value <= stat["maximum"]: return "ABOVE_P75"
    return "ABOVE_MAX"


def _reliability(n):
    return "usable" if n >= 5 else "indicative" if n >= 3 else "insufficient"


def _comment(position, reliability, gap):
    labels = {
        "BELOW_MIN": "valeur inférieure au minimum des pairs",
        "BELOW_P25": "valeur inférieure au premier quartile",
        "P25_P75": "valeur dans la plage centrale P25–P75",
        "ABOVE_P75": "valeur supérieure au troisième quartile",
        "ABOVE_MAX": "valeur supérieure au maximum des pairs",
        "PROJECT_VALUE_UNAVAILABLE": "valeur du projet non calculable dans la même unité",
        "NO_PEER_DATA": "aucune donnée disponible chez les pairs approuvés",
    }
    text = labels[position]
    if gap is not None: text += f"; écart à la médiane {gap:+.1%}"
    if reliability == "insufficient": text += "; échantillon insuffisant pour conclure"
    elif reliability == "indicative": text += "; comparaison indicative"
    return text + "."


def load_peer_selection(path):
    path = Path(path)
    if not path.exists(): return None
    with path.open(encoding="utf-8-sig") as stream: data = json.load(stream)
    if not isinstance(data, dict) or "approved_project_ids" not in data:
        raise ValueError("Le fichier de comparables ne respecte pas le format de l'étape 5.")
    return data


def position_project(selection, registre, indicateurs):
    if selection is None:
        return {"status": "NOT_PERFORMED", "reason": "comparable_selection.json absent",
                "approved_count": 0, "comparisons": [], "approved_projects": []}
    approved_ids = selection.get("approved_project_ids") or []
    stats = {item.get("metric"): item for item in selection.get("benchmark_statistics", [])}
    derived = {item.get("cle"): item.get("valeur") for item in indicateurs}
    raw = {item.get("cle"): item.get("valeur") for item in registre}
    total_mw = derived.get("total_investment_per_mw")
    project_values = {"total_investment_per_mw": total_mw,
                      "total_investment_per_kw": total_mw / 1000 if total_mw is not None else None,
                      "debt_share": derived.get("debt_share"), "equity_share": derived.get("equity_share"),
                      "contract_period_years": raw.get("duree_concession"), "private_ownership_share": None}
    comparisons = []
    for metric, (label, project_key) in METRICS.items():
        stat = stats.get(metric)
        if not stat: continue
        value, n = project_values.get(project_key), int(stat.get("sample_size") or 0)
        reliability, position, median = _reliability(n), _position(value, stat), stat.get("median")
        gap = value / median - 1 if value is not None and median not in (None, 0) else None
        comparisons.append({"metric": metric, "label": label, "project_value": value,
            "unit": stat.get("unit"), "sample_size": n, "minimum": stat.get("minimum"),
            "p25": stat.get("p25"), "median": median, "mean": stat.get("mean"),
            "p75": stat.get("p75"), "maximum": stat.get("maximum"), "position": position,
            "gap_to_median": gap, "reliability": reliability, "comment": _comment(position, reliability, gap),
            "peer_project_ids": stat.get("project_ids") or []})
    decisions = selection.get("decisions") or []
    return {"status": "APPLIED" if approved_ids else "NO_APPROVED_PROJECTS",
        "selection_status": selection.get("selection_status"), "approved_count": len(approved_ids),
        "approved_project_ids": approved_ids,
        "approved_projects": [x for x in decisions if x.get("decision") == "approved"],
        "comparisons": comparisons}


def _value_text(value, unit):
    if value is None: return "Non calculable"
    if unit == "ratio": return f"{100 * value:.1f} %"
    return f"{value:,.2f} {unit or ''}".replace(",", " ").strip()


def _range_text(item):
    return (f"P25 {_value_text(item.get('p25'), item.get('unit'))}; "
            f"médiane {_value_text(item.get('median'), item.get('unit'))}; "
            f"P75 {_value_text(item.get('p75'), item.get('unit'))} (n={item.get('sample_size')})")


def enrich_benchmark_table(rows, peer_result):
    comparisons = {item["metric"]: item for item in peer_result.get("comparisons", [])}
    total = comparisons.get("investment_per_kw_usd")
    if total:
        target = next((r for r in rows if "total du projet par kW" in r.get("cout", "")), None)
        if target:
            target["valeurs_projets_region"], target["commentaires"] = _range_text(total), total["comment"]
    for metric in ("debt_share", "equity_share", "contract_period_years", "private_ownership_share"):
        item = comparisons.get(metric)
        if item:
            rows.append({"cout": item["label"], "valeurs_standards": "Aucune norme sectorielle appliquée",
                "valeurs_projets_region": _range_text(item),
                "couts_projet_gds": _value_text(item.get("project_value"), item.get("unit")),
                "commentaires": item["comment"]})
    return rows


def enrich_professional_analysis(analysis, peer_result):
    """Add cautious deterministic peer conclusions to the professional opinion."""
    if peer_result.get("status") != "APPLIED":
        return analysis
    comparisons = peer_result.get("comparisons", [])
    usable = [x for x in comparisons if x["reliability"] in {"usable", "indicative"}
              and x["position"] not in {"PROJECT_VALUE_UNAVAILABLE", "NO_PEER_DATA"}]
    deviations = [x for x in usable if x["position"] in {"BELOW_MIN", "ABOVE_MAX"}]
    count = peer_result.get("approved_count", 0)
    sentence = f"La comparaison par projets pairs repose sur {count} projet(s) approuvé(s) par l'analyste."
    if deviations:
        sentence += " Écart(s) hors plage observée : " + ", ".join(x["label"] for x in deviations) + "."
    elif usable:
        sentence += " Aucun indicateur comparable exploitable ne se situe hors de la plage min–max des pairs."
    analysis["synthese_executive"] += " " + sentence
    for item in deviations:
        analysis["risques"].append(f"Benchmark pairs — {item['label']} : {item['comment']}")
    insufficient = [x["label"] for x in comparisons if x["reliability"] == "insufficient"]
    if insufficient:
        analysis["recommandations"].append(
            "Élargir ou documenter l'échantillon de pairs pour : " + ", ".join(insufficient) + "."
        )
    unavailable = [x["label"] for x in comparisons if x["position"] == "PROJECT_VALUE_UNAVAILABLE"]
    if unavailable:
        analysis["recommandations"].append(
            "Compléter les unités et conversions validées pour positionner : " + ", ".join(unavailable) + "."
        )
    return analysis
