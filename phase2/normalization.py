"""Unit and perimeter checks used before a benchmark is applied."""

from __future__ import annotations


UNIT_ALIASES = {
    "%": "ratio", "percentage": "ratio", "decimal": "ratio", "ratio": "ratio",
    "years": "year", "ans": "year", "year": "year",
    "currency/mw": "currency/MW", "currency/MW": "currency/MW",
    "currency/year": "currency/year",
    "usd/mw": "USD/MW", "USD/MW": "USD/MW",
}


def canonical_unit(unit):
    if unit is None:
        return None
    text = str(unit).strip()
    return UNIT_ALIASES.get(text, UNIT_ALIASES.get(text.lower(), text))


def verifier_comparabilite(indicateur, norme, contexte=None):
    raisons = []
    contexte = contexte or {}
    if indicateur.get("assumptions"):
        raisons.append("hypothèses d'unité non confirmées")
    if not norme.get("approved", False):
        raisons.append("référence non approuvée")
    if canonical_unit(indicateur.get("unite")) != canonical_unit(norme.get("unit")):
        raisons.append("unités incompatibles")
    for field in ("technology", "geography", "currency", "price_year", "data_year"):
        attendu = norme.get(field)
        observe = contexte.get("benchmark_currency") if field == "currency" else contexte.get(field)
        if field == "currency" and observe is None:
            observe = contexte.get("currency")
        if field == "geography" and str(attendu).lower() == "global":
            continue
        if attendu is not None and observe is None:
            raisons.append(f"contexte {field} manquant")
        elif attendu is not None and observe != attendu:
            raisons.append(f"{field} incompatible")
    return {"comparable": not raisons, "raisons": raisons}
