"""Deterministic comparison of derived indicators with approved references."""

from __future__ import annotations

from .normalization import verifier_comparabilite


def _verdict(value, low, high):
    if low is not None and value < low:
        return "BELOW"
    if high is not None and value > high:
        return "ABOVE"
    return "WITHIN"


def _point_verdict(value, target, tolerance=0.0):
    if abs(value - target) <= tolerance:
        return "AT_REFERENCE"
    return "BELOW_REFERENCE" if value < target else "ABOVE_REFERENCE"


def comparer(indicateurs, referentiel, contexte=None):
    par_cle = {item["cle"]: item for item in indicateurs}
    resultats = []
    for norme in referentiel.get("normes", []):
        cle = norme.get("applies_to")
        indicateur = par_cle.get(cle)
        base = {
            "benchmark_key": norme.get("cle"),
            "indicator_key": cle,
            "source": norme.get("source"),
            "source_url": norme.get("source_url"),
            "edition_year": norme.get("edition_year"),
            "perimeter": norme.get("perimeter"),
            "low": norme.get("low"),
            "high": norme.get("high"),
            "target": norme.get("target"),
            "comparison_type": norme.get("comparison_type", "range"),
            "unit": norme.get("unit"),
        }
        contexte_effectif = contexte or {}
        technologie = norme.get("technology")
        geographie = norme.get("geography")
        if (technologie and contexte_effectif.get("technology")
                and technologie != contexte_effectif["technology"]):
            resultats.append({**base, "value": indicateur.get("valeur") if indicateur else None,
                              "status": "NOT_APPLICABLE", "verdict": None,
                              "reasons": ["technologie hors périmètre"]})
            continue
        if (geographie and str(geographie).lower() != "global"
                and contexte_effectif.get("geography")
                and geographie != contexte_effectif["geography"]):
            resultats.append({**base, "value": indicateur.get("valeur") if indicateur else None,
                              "status": "NOT_APPLICABLE", "verdict": None,
                              "reasons": ["géographie hors périmètre"]})
            continue
        if not indicateur or not indicateur.get("calculable"):
            resultats.append({**base, "value": None, "status": "NOT_CALCULABLE",
                              "verdict": None, "reasons": ["données d'entrée manquantes"]})
            continue
        controle = verifier_comparabilite(indicateur, norme, contexte)
        if not controle["comparable"]:
            resultats.append({**base, "value": indicateur["valeur"],
                              "status": "NOT_COMPARABLE", "verdict": None,
                              "reasons": controle["raisons"]})
            continue
        if norme.get("comparison_type") == "point":
            target = norme.get("target")
            if target is None:
                resultats.append({**base, "value": indicateur["valeur"],
                                  "status": "INVALID_REFERENCE", "verdict": None,
                                  "reasons": ["target manquant"]})
                continue
            verdict = _point_verdict(indicateur["valeur"], target, norme.get("tolerance", 0.0))
            deviation = (indicateur["valeur"] / target - 1.0) if target else None
        else:
            verdict = _verdict(indicateur["valeur"], norme.get("low"), norme.get("high"))
            deviation = None
        resultats.append({**base, "value": indicateur["valeur"], "status": "COMPARED",
                          "verdict": verdict, "deviation_from_reference": deviation,
                          "reasons": []})
    return resultats
