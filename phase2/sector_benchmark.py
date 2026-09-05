"""Select applicable IRENA sector observations from the active benchmark bank."""

from __future__ import annotations

import json
from pathlib import Path

from benchmark_bank.storage import BenchmarkRepository


CORE_METRICS = ("total_installed_cost", "capacity_factor", "lcoe", "economic_life", "wacc")


def _registry(registry): return {item.get("cle"): item for item in registry}
def _derived(indicators): return {item.get("cle"): item.get("valeur") for item in indicators}


def _preferred(items, metric, geography):
    candidates = [item for item in items if item["metric"] == metric]
    if not candidates: return None
    def score(item):
        exact = str(item["geography"]).casefold() == str(geography or "").casefold()
        global_value = str(item["geography"]).casefold() == "global"
        headline = "Table S.1" in item["source_location"]
        return (exact, global_value, headline, item.get("value_date") or "")
    return max(candidates, key=score)


def load_irena_sector_benchmark(database_path, technology, geography=None):
    path = Path(database_path)
    if not path.exists():
        return {"status":"UNAVAILABLE", "reason":"active benchmark database absent", "references":[]}
    with BenchmarkRepository(path, read_only=True) as repository:
        rows = repository.connection.execute(
            """SELECT observation_id, metric, normalized_value, normalized_low, normalized_high,
                      normalized_unit, statistic, source_id, payload_json
               FROM current_observations
               WHERE observation_type='sector_statistic'"""
        ).fetchall()
    observations = []
    for row in rows:
        payload = json.loads(row[8]); metadata = payload.get("metadata") or {}
        if metadata.get("technology") != technology: continue
        observations.append({"observation_id":row[0], "metric":row[1], "value":row[2],
            "low":row[3], "high":row[4], "unit":row[5], "statistic":row[6], "source_id":row[7],
            "geography":metadata.get("geography", "global"), "value_date":payload.get("value_date"),
            "source_location":payload.get("source_location"), "perimeter":payload.get("economic_perimeter")})
    references = [item for metric in CORE_METRICS if (item := _preferred(observations, metric, geography))]
    return {"status":"APPLIED" if references else "NO_APPLICABLE_REFERENCE",
            "technology":technology, "geography":geography, "references":references,
            "source_observation_count":len(observations)}


def position_against_irena(sector, registry, indicators, context=None):
    if sector.get("status") != "APPLIED": return {**sector, "comparisons":[]}
    context = context or {}; raw, derived = _registry(registry), _derived(indicators)
    project = {
        "capacity_factor": derived.get("capacity_factor"),
        "wacc": (raw.get("wacc") or {}).get("valeur"),
    }
    construction = (raw.get("cout_construction") or {}).get("valeur")
    capacity = (raw.get("puissance") or {}).get("valeur")
    rate = context.get("usd_per_currency_unit")
    if isinstance(construction, (int,float)) and isinstance(capacity, (int,float)) and capacity and rate:
        project["total_installed_cost"] = construction * float(rate) / (capacity * 1000)
    comparisons = []
    for ref in sector["references"]:
        value = project.get(ref["metric"]); target = ref.get("value")
        comparable = value is not None and target not in (None, 0) and ref["metric"] in project
        gap = value / target - 1 if comparable else None
        comparisons.append({**ref, "project_value":value, "comparable":comparable,
            "gap_to_reference":gap, "position":("ABOVE" if gap is not None and gap > 0 else
                "BELOW" if gap is not None and gap < 0 else "EQUAL" if gap == 0 else "CONTEXT_ONLY"),
            "comment":("Comparaison calculée sur une unité compatible." if comparable else
                "Référence sectorielle informative; valeur ou conversion compatible indisponible.")})
    return {**sector, "comparisons":comparisons}


def enrich_sector_table(rows, sector_result):
    refs = {item["metric"]:item for item in sector_result.get("references", [])}
    mapping = {"Coût de construction par kW":"total_installed_cost",
               "Facteur de charge":"capacity_factor", "Tarif / coût de l'énergie":"lcoe"}
    for row in rows:
        metric = mapping.get(row.get("cout")); ref = refs.get(metric)
        if not ref: continue
        value = ref.get("value"); unit = ref.get("unit") or ""
        if unit == "ratio" and value is not None: display = f"{100*value:.1f} %"
        else: display = f"{value:,.3f} {unit}".replace(",", " ") if value is not None else "Non disponible"
        row["valeurs_standards"] = f"{display} — IRENA, {ref['source_location']}"
    return rows
