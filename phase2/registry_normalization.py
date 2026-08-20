"""Non-destructive normalization of the analyst-validated Phase 1 registry."""

import re


UNITS_BY_KEY = {
    "gearing": "ratio", "duree_dette": "year", "dscr_cible": "x",
    "is_taux": "ratio", "tva": "ratio", "wht": "ratio",
    "amortissement_duree": "year", "tri_projet": "ratio",
    "tri_fonds_propres": "ratio", "wacc": "ratio",
    "taux_actualisation": "ratio", "duree_construction": "month",
    "duree_concession": "year", "disponibilite": "ratio",
}


def _parse_number(value):
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        return float(value)
    if not isinstance(value, str):
        return None
    match = re.search(r"[-+]?\d[\d\s\u00a0\u202f]*(?:[.,]\d+)?", value)
    if not match:
        return None
    token = re.sub(r"[\s\u00a0\u202f]", "", match.group(0))
    token = token.replace(",", ".") if "," in token and "." not in token else token.replace(",", "")
    try:
        return float(token)
    except ValueError:
        return None


def _unit_for(item, context):
    key = item.get("cle")
    if key in {"cout_construction", "investissement_total"}:
        return context.get("currency") or "currency"
    if key == "opex_1":
        return f"{context.get('currency') or 'currency'}/year"
    if key == "puissance":
        return context.get("power_unit") or "MW"
    if key == "productible":
        return context.get("productible_unit") or "MWh/year"
    if key == "tarif":
        raw = str(item.get("valeur") or "")
        return raw.split(maxsplit=1)[1] if " " in raw else context.get("tariff_unit")
    return UNITS_BY_KEY.get(key, item.get("unite"))


def normaliser_registre(registre, contexte=None):
    contexte = contexte or {}
    normalized, warnings = [], []
    for original in registre:
        item = dict(original)
        raw = original.get("valeur")
        item["valeur_originale"] = raw
        item["unite"] = _unit_for(original, contexte)
        item["normalisation_warnings"] = []
        if raw is None or isinstance(raw, (list, dict)):
            item["valeur"] = raw
        else:
            parsed = _parse_number(raw)
            if parsed is None:
                item["valeur"] = raw
                item["normalisation_warnings"].append("valeur scalaire non interprétable")
            else:
                if original.get("nature") == "taux" and abs(parsed) > 1:
                    parsed /= 100.0
                item["valeur"] = parsed
        if item["normalisation_warnings"]:
            warnings.append({"cle": item.get("cle"), "warnings": item["normalisation_warnings"]})
        normalized.append(item)
    return normalized, warnings
