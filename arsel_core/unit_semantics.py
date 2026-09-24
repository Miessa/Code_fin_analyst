# -*- coding: utf-8 -*-
"""Détection, décomposition et compatibilité des unités de Phase 1.

La qualité de la cellule candidate et celle de son unité sont volontairement
séparées. Une unité contradictoire peut être mal rattachée spatialement : elle
ne doit donc jamais éliminer à elle seule une cellule par ailleurs plausible.
"""

from __future__ import annotations

import re
import unicodedata


_CURRENCY = {
    "eur": "EUR", "€": "EUR",
    "usd": "USD", "$": "USD",
    "xaf": "XAF", "fcfa": "XAF", "cfa": "XAF",
}

_PERIODS = (
    (r"(?:/|\bper\s+|\bpar\s+)(?:year|yr|an|année)\b|\bp\.?\s*a\.?\b|\bannual(?:ly)?\b|\bannuel(?:le)?\b", "annual"),
    (r"(?:/|\bper\s+|\bpar\s+)(?:month|mois)\b|\bmonthly\b|\bmensuel(?:le)?\b", "monthly"),
    (r"(?:/|\bper\s+|\bpar\s+)(?:day|jour)\b|\bdaily\b|\bjournalier(?:e)?\b", "daily"),
    (r"(?:/|\bper\s+|\bpar\s+)(?:quarter|trimestre)\b|\bquarterly\b|\btrimestriel(?:le)?\b", "quarterly"),
)

_ENERGY = {"wh": "Wh", "kwh": "kWh", "mwh": "MWh", "gwh": "GWh", "twh": "TWh"}
_POWER = {"w": "W", "kw": "kW", "mw": "MW", "gw": "GW"}
_DURATION = {
    "day": "day", "days": "day", "jour": "day", "jours": "day",
    "month": "month", "months": "month", "mois": "month",
    "year": "year", "years": "year", "yr": "year", "yrs": "year",
    "an": "year", "ans": "year", "année": "year", "années": "year",
}


def _plain(value):
    value = unicodedata.normalize("NFD", str(value or "").lower())
    return "".join(c for c in value if unicodedata.category(c) != "Mn")


def decompose_unit(text):
    """Return structured semantics for a unit expression, or ``None``.

    The returned ``raw_unit`` is deliberately concise.  The complete source
    text remains available on the spatial candidate for audit purposes.
    """
    original = str(text or "").strip()
    if not original:
        return None
    normalized = _plain(original).replace("’", "'")

    currency = None
    currency_token = None
    for token, code in _CURRENCY.items():
        pattern = re.escape(token) if token in ("€", "$") else rf"(?<![a-z]){re.escape(token)}(?![a-z])"
        if re.search(pattern, normalized, re.I):
            currency, currency_token = code, token
            break

    scale = 1
    scale_token = None
    if re.search(r"(?:['’]\s*0{3}s?\b|\b0{3}s?\b|\bthousand(?:s)?\b|\bmillier(?:s)?\b|\bk\s*(?:eur|usd|xaf|fcfa|cfa|€|$)\b)", normalized, re.I):
        scale, scale_token = 1_000, "thousand"
    elif re.search(r"\b(?:million(?:s)?|mn|mio)\b", normalized, re.I):
        scale, scale_token = 1_000_000, "million"
    elif re.search(r"\b(?:billion(?:s)?|milliard(?:s)?|bn)\b", normalized, re.I):
        scale, scale_token = 1_000_000_000, "billion"

    periodicity = None
    for pattern, value in _PERIODS:
        if re.search(pattern, normalized, re.I):
            periodicity = value
            break

    percent = bool(re.search(r"%|\bpercent(?:age)?\b|\bpour\s*cent\b", normalized, re.I))
    multiple = bool(re.search(r"(?<![a-z0-9])x(?![a-z])|\btimes?\b|\bmultiple\b", normalized, re.I))

    energy = None
    power = None
    # Energy must be tested before power because MWh contains MW.
    for token, canonical in _ENERGY.items():
        if re.search(rf"(?<![a-z]){token}(?![a-z])", normalized, re.I):
            energy = canonical
            break
    if not energy:
        for token, canonical in _POWER.items():
            if re.search(rf"(?<![a-z]){token}(?![a-z])", normalized, re.I):
                power = canonical
                break

    duration = None
    for token, canonical in _DURATION.items():
        if re.search(rf"(?<![a-z]){re.escape(_plain(token))}(?![a-z])", normalized, re.I):
            duration = canonical
            break

    denominator = None
    denominator_match = re.search(
        r"/(?:\s*)(kwh|mwh|gwh|kw|mw|gw|day|days|jour|jours|month|months|mois|year|years|yr|an|ans)\b",
        normalized,
        re.I,
    )
    if denominator_match:
        denominator = denominator_match.group(1)

    canonical_denominator = (
        _ENERGY.get((denominator or "").lower())
        or _POWER.get((denominator or "").lower())
        or _DURATION.get((denominator or "").lower())
    )

    if currency and canonical_denominator in set(_ENERGY.values()) | set(_POWER.values()):
        family = "tariff_rate"
        quantity_type = "tariff"
    elif currency and periodicity:
        family = "currency_per_year" if periodicity == "annual" else "currency_flow"
        quantity_type = "currency_flow"
    elif currency:
        family, quantity_type = "currency_amount", "currency_amount"
    elif percent:
        family, quantity_type = "percentage_rate", "rate"
    elif multiple:
        family, quantity_type = "multiple_ratio", "ratio"
    elif energy:
        family, quantity_type = "energy", "energy"
    elif power:
        family, quantity_type = "power", "power"
    elif duration:
        family, quantity_type = "duration", "duration"
    else:
        return None

    pieces = []
    if currency:
        pieces.append(currency)
    if scale_token:
        pieces.append(scale_token)
    if percent:
        pieces.append("%")
    if multiple:
        pieces.append("x")
    # A unit found after '/' is a denominator, not a second numerator.
    if energy and not denominator:
        pieces.append(energy)
    elif power and not denominator:
        pieces.append(power)
    elif duration and not currency:
        pieces.append(duration)
    if denominator:
        pieces.append(f"/{canonical_denominator or denominator}")
    if periodicity:
        period_label = {
            "annual": "year", "monthly": "month",
            "quarterly": "quarter", "daily": "day",
        }.get(periodicity, periodicity)
        if canonical_denominator != period_label:
            pieces.append(f"/{period_label}")

    return {
        "raw_unit": original,
        "unit_expression": " ".join(pieces),
        "quantity_type": quantity_type,
        "family": family,
        "currency": currency,
        "scale": scale,
        "periodicity": periodicity,
        "denominator": canonical_denominator or denominator,
    }


def unit_contract(concept):
    """Build the metric-specific contract from its ARSEL reference entry."""
    expected = concept.get("famille_unite") or "unknown"
    aliases = {
        "percentage_ratio": {"percentage_rate"},
        "percentage_rate": {"percentage_rate"},
        "duration_years": {"duration"},
        "duration_months": {"duration"},
        "currency_per_year": {"currency_per_year", "currency_flow", "currency_amount"},
        "currency_amount": {"currency_amount", "currency_per_year", "currency_flow"},
        "multiple_ratio": {"multiple_ratio"},
        "tariff_rate": {"tariff_rate"},
        "energy": {"energy"},
        "power": {"power"},
    }
    accepted = set(concept.get("familles_unite_acceptees") or aliases.get(expected, {expected}))
    preferred_period = concept.get("periodicite_preferee")
    if not preferred_period:
        scope = concept.get("portee_temporelle")
        if scope in {"annual", "year_1"}:
            preferred_period = "annual"
    return {
        "expected_family": expected,
        "accepted_families": sorted(accepted),
        "preferred_periodicity": preferred_period,
    }


def compatibility(unit, concept):
    """Assess an already decomposed unit against one metric contract."""
    contract = unit_contract(concept)
    family = (unit or {}).get("family", "unknown")
    compatible = family in contract["accepted_families"]
    period = (unit or {}).get("periodicity")
    preferred = contract.get("preferred_periodicity")
    periodicity_status = (
        "compatible" if not preferred or period == preferred
        else "unknown" if period is None
        else "incompatible"
    )
    return {
        "compatible": compatible,
        "family_status": "compatible" if compatible else "incompatible",
        "periodicity_status": periodicity_status,
        "contract": contract,
    }


def choose_unit_for_metric(candidate, concept):
    """Attach the best unit hypothesis without changing candidate eligibility."""
    choices = []
    for spatial in candidate.get("unit_candidates") or []:
        semantics = spatial.get("semantics") or decompose_unit(spatial.get("source_text"))
        if not semantics:
            continue
        assessment = compatibility(semantics, concept)
        spatial_score = float(spatial.get("attachment_confidence", 0.0))
        # Compatibility helps choose between unit hypotheses; it never changes
        # the retrieval/metric score and therefore cannot remove the cell.
        choice_score = spatial_score + (0.35 if assessment["compatible"] else 0.0)
        choices.append({
            **spatial,
            "semantics": semantics,
            "compatibility": assessment,
            "unit_choice_score": round(choice_score, 4),
        })
    choices.sort(key=lambda item: item["unit_choice_score"], reverse=True)
    compatible_choices = [c for c in choices if c["compatibility"]["compatible"]]
    selected = compatible_choices[0] if compatible_choices else (choices[0] if choices else None)

    result = {**candidate, "unit_candidates": choices}
    if selected:
        result["unit_selected"] = selected
        result["unit_compatibility"] = selected["compatibility"]
        result["unit_attachment_confidence"] = selected.get("attachment_confidence", 0.0)
        if selected["compatibility"]["compatible"]:
            semantics = dict(selected["semantics"])
            preferred = selected["compatibility"]["contract"].get("preferred_periodicity")
            if not semantics.get("periodicity") and preferred:
                context = " | ".join(str(candidate.get(k) or "") for k in (
                    "libelle", "section", "contexte", "contexte_haut"
                ))
                for pattern, period in _PERIODS:
                    if re.search(pattern, _plain(context), re.I):
                        semantics["periodicity"] = period
                        semantics["periodicity_source"] = "metric_context"
                        period_label = {
                            "annual": "year", "monthly": "month",
                            "quarterly": "quarter", "daily": "day",
                        }.get(period, period)
                        if f"/{period_label}" not in semantics["unit_expression"]:
                            semantics["unit_expression"] += f" /{period_label}"
                        break
            result["unit_semantics"] = semantics
            result["unit_conflict_semantics"] = None
            result["unite_detectee"] = semantics["unit_expression"]
            result["unit_status"] = "confirmed"
        else:
            # Preserve the conflicting hypothesis for audit, but do not expose
            # it as if it were the unit of the otherwise valid metric.
            result["unit_semantics"] = None
            result["unit_conflict_semantics"] = selected["semantics"]
            result["unite_detectee"] = None
            result["unit_status"] = "conflict_metric_kept"
    else:
        result.update({
            "unit_selected": None,
            "unit_semantics": None,
            "unit_conflict_semantics": None,
            "unit_compatibility": {
                "compatible": False,
                "family_status": "unknown",
                "periodicity_status": "unknown",
                "contract": unit_contract(concept),
            },
            "unit_attachment_confidence": 0.0,
            "unite_detectee": None,
            "unit_status": "unknown_metric_kept",
        })
    return result
