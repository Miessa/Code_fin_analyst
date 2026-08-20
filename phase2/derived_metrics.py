"""Compute auditable indicators from the validated Phase 1 registry."""

from __future__ import annotations


CANONICAL_UNITS = {
    "cout_construction": "currency",
    "investissement_total": "currency",
    "opex_1": "currency/year",
    "puissance": "MW",
    "productible": "MWh/year",
    "gearing": "ratio",
    "tri_projet": "ratio",
    "tri_fonds_propres": "ratio",
    "wacc": "ratio",
    "taux_actualisation": "ratio",
    "duree_dette": "year",
    "duree_concession": "year",
}


def _number(value):
    return isinstance(value, (int, float)) and not isinstance(value, bool)


def _scalar(index, key):
    item = index.get(key) or {}
    value = item.get("valeur")
    return float(value) if _number(value) else None


def _ratio(value):
    """Registry rates are normally decimals; tolerate analyst-entered percentages."""
    if value is None:
        return None
    return value / 100.0 if abs(value) > 1.0 else value


def _indicator(key, value, unit, inputs, formula, assumptions=None):
    return {
        "cle": key,
        "valeur": value,
        "unite": unit,
        "inputs": inputs,
        "formule": formula,
        "assumptions": assumptions or [],
        "calculable": value is not None,
    }


def calculer_indicateurs(registre, contexte=None):
    contexte = contexte or {}
    index = {item.get("cle"): item for item in registre if item.get("cle")}
    capex = _scalar(index, "cout_construction")
    investissement = _scalar(index, "investissement_total")
    puissance = _scalar(index, "puissance")
    productible = _scalar(index, "productible")
    opex = _scalar(index, "opex_1")
    gearing = _ratio(_scalar(index, "gearing"))
    tri_projet = _ratio(_scalar(index, "tri_projet"))
    tri_equity = _ratio(_scalar(index, "tri_fonds_propres"))
    wacc = _ratio(_scalar(index, "wacc"))
    actualisation = _ratio(_scalar(index, "taux_actualisation"))
    duree_dette = _scalar(index, "duree_dette")
    concession = _scalar(index, "duree_concession")

    def div(a, b):
        return a / b if a is not None and b not in (None, 0) else None

    reference_rentabilite = wacc if wacc is not None else actualisation
    monetary_scale = contexte.get("monetary_scale")
    currency = str(contexte.get("currency") or "").upper()
    usd_rate = contexte.get("usd_per_currency_unit")
    if currency == "USD" and usd_rate is None:
        usd_rate = 1.0
    capex_usd = (
        capex * float(monetary_scale) * float(usd_rate)
        if capex is not None and monetary_scale is not None and usd_rate is not None
        else None
    )
    capex_assumptions = [] if capex_usd is not None else [
        "Renseigner currency, monetary_scale et usd_per_currency_unit dans le contexte."
    ]

    productible_unit = str(contexte.get("productible_unit") or "").upper()
    power_unit = str(contexte.get("power_unit") or "").upper()
    energy_factor = {"KWH/YEAR": .001, "MWH/YEAR": 1.0, "GWH/YEAR": 1000.0}.get(productible_unit)
    power_factor = {"KW": .001, "MW": 1.0, "GW": 1000.0}.get(power_unit)
    capacity_factor = (
        productible * energy_factor / (puissance * power_factor * 8760.0)
        if productible is not None and puissance not in (None, 0)
        and energy_factor is not None and power_factor is not None else None
    )

    indicateurs = [
        _indicator("construction_share", div(capex, investissement), "ratio",
                   ["cout_construction", "investissement_total"],
                   "cout_construction / investissement_total"),
        _indicator("non_construction_share",
                   1.0 - div(capex, investissement) if div(capex, investissement) is not None else None,
                   "ratio", ["cout_construction", "investissement_total"],
                   "1 - construction_share"),
        _indicator("capex_per_mw", div(capex_usd, puissance), "USD/MW",
                   ["cout_construction", "puissance"],
                   "cout_construction * monetary_scale * usd_per_currency_unit / puissance_MW",
                   capex_assumptions),
        _indicator("opex_to_capex", div(opex, capex), "ratio/year",
                   ["opex_1", "cout_construction"], "opex_1 / cout_construction"),
        _indicator("debt_share", gearing, "ratio", ["gearing"], "gearing"),
        _indicator("equity_share", 1.0 - gearing if gearing is not None else None,
                   "ratio", ["gearing"], "1 - gearing"),
        _indicator("project_irr_spread", tri_projet - reference_rentabilite
                   if tri_projet is not None and reference_rentabilite is not None else None,
                   "ratio", ["tri_projet", "wacc" if wacc is not None else "taux_actualisation"],
                   "tri_projet - reference_rate"),
        _indicator("equity_irr_premium", tri_equity - tri_projet
                   if tri_equity is not None and tri_projet is not None else None,
                   "ratio", ["tri_fonds_propres", "tri_projet"],
                   "tri_fonds_propres - tri_projet"),
        _indicator("debt_tail", concession - duree_dette
                   if concession is not None and duree_dette is not None else None,
                   "year", ["duree_concession", "duree_dette"],
                   "duree_concession - duree_dette"),
        _indicator("capacity_factor", capacity_factor,
                   "ratio", ["productible", "puissance"],
                   "productible_MWh / (puissance_MW * 8760)",
                   [] if capacity_factor is not None else
                   ["Renseigner productible_unit et power_unit dans le contexte."]),
        _indicator("wacc", wacc, "ratio", ["wacc"], "wacc"),
        _indicator("dscr_cible", _scalar(index, "dscr_cible"), "x",
                   ["dscr_cible"], "dscr_cible"),
        _indicator("tri_fonds_propres", tri_equity, "ratio",
                   ["tri_fonds_propres"], "tri_fonds_propres"),
    ]
    return indicateurs
