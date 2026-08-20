"""Build the regulator-facing benchmark table from detailed source observations."""


def _index(items, key):
    return {item[key]: item for item in items}


def _pct(value, digits=1):
    return f"{100 * value:.{digits}f} %"


def _money_per_kw(amount, capacity, currency):
    if amount is None or capacity in (None, 0):
        return None
    return f"{amount / (capacity * 1000):,.0f} {currency}/kW".replace(",", " ")


def construire_tableau(registre, indicateurs, referentiel, contexte=None):
    contexte = contexte or {}
    metrics = {x["cle"]: x.get("valeur") for x in registre}
    derived = {x["cle"]: x.get("valeur") for x in indicateurs}
    observations = _index(referentiel.get("observations", []), "observation_id")
    projects = _index(referentiel.get("projects", []), "project_id")
    technology = contexte.get("technology")
    currency = contexte.get("currency") or "currency"
    capacity = metrics.get("puissance")
    sahofika = projects.get("sahofika_hydropower_madagascar", {}) if technology == "hydropower" else {}

    def observation(identifier, field="value"):
        return (observations.get(identifier) or {}).get(field)

    construction_per_kw = _money_per_kw(metrics.get("cout_construction"), capacity, currency)
    total_per_kw = _money_per_kw(metrics.get("investissement_total"), capacity, currency)
    om_ratio = derived.get("opex_to_capex")
    project_cf = derived.get("capacity_factor")
    equity_irr = derived.get("tri_fonds_propres")
    dscr = derived.get("dscr_cible")
    tariff_item = next((x for x in registre if x.get("cle") == "tarif"), {})
    tariff = tariff_item.get("valeur")
    tariff_unit = tariff_item.get("unite") or ""

    rows = []
    if technology == "hydropower":
        standard_cost = observation("irena_hydro_tic_2024")
        standard_cf = observation("irena_hydro_capacity_factor_2024")
        standard_lcoe = observation("irena_hydro_lcoe_2024")
        standard_om_low = observation("irena_hydro_om_share_range", "low")
        standard_om_high = observation("irena_hydro_om_share_range", "high")
    else:
        standard_cost = standard_cf = standard_lcoe = standard_om_low = standard_om_high = None

    rows.append({
        "cout": "Coût de construction par kW",
        "valeurs_standards": f"{standard_cost:,.0f} USD/kW — moyenne mondiale IRENA 2024".replace(",", " ") if standard_cost else "Non disponible",
        "valeurs_projets_region": "Non publié dans les projets hydro régionaux retenus",
        "couts_projet_gds": construction_per_kw or "Non calculable",
        "commentaires": "Comparaison indicative seulement: conversion EUR/USD et année de prix requises." if construction_per_kw else "Capacité ou coût de construction manquant."
    })
    rows.append({
        "cout": "Coût total du projet par kW",
        "valeurs_standards": "Non disponible dans les observations retenues",
        "valeurs_projets_region": "Non publié de manière comparable",
        "couts_projet_gds": total_per_kw or "Non calculable",
        "commentaires": "L'investissement total inclut des coûts hors EPC; il ne doit pas être comparé directement au coût installé IRENA."
    })
    rows.append({
        "cout": "Charges O&M / coût de construction",
        "valeurs_standards": f"{_pct(standard_om_low, 0)}–{_pct(standard_om_high, 0)} par an — IRENA" if standard_om_low is not None else "Non disponible",
        "valeurs_projets_region": "Montant O&M non publié pour Sahofika",
        "couts_projet_gds": f"{_pct(om_ratio, 2)} par an" if om_ratio is not None else "Non calculable",
        "commentaires": "La valeur GDS se situe dans la plage historique IRENA." if om_ratio is not None and standard_om_low <= om_ratio <= standard_om_high else "Vérifier que les périmètres O&M sont identiques."
    })
    rows.append({
        "cout": "Facteur de charge",
        "valeurs_standards": f"{_pct(standard_cf)} — moyenne mondiale IRENA 2024" if standard_cf is not None else "Non disponible",
        "valeurs_projets_region": "Non publié dans Sahofika",
        "couts_projet_gds": _pct(project_cf) if project_cf is not None else "Non calculable",
        "commentaires": "Supérieur au point IRENA; corroborer par les études hydrologiques." if project_cf is not None and standard_cf is not None and project_cf > standard_cf else "Écart non déterminé."
    })
    regional_irr = ((sahofika.get("metrics") or {}).get("equity_irr") or {}).get("value")
    rows.append({
        "cout": "TRI fonds propres",
        "valeurs_standards": "Aucune norme sectorielle approuvée",
        "valeurs_projets_region": f"Sahofika: jusqu'à {_pct(regional_irr)} nominal" if regional_irr is not None else "Non disponible",
        "couts_projet_gds": _pct(equity_irr, 2) if equity_irr is not None else "Non disponible",
        "commentaires": "Sahofika est un projet pair, pas une norme; comparer aussi risques, fiscalité et levier."
    })
    regional_dscr = ((sahofika.get("metrics") or {}).get("minimum_dscr") or {}).get("value")
    rows.append({
        "cout": "DSCR",
        "valeurs_standards": "Aucune norme ARSEL fournie",
        "valeurs_projets_region": f"Sahofika: minimum {regional_dscr:.2f}x" if regional_dscr is not None else "Non disponible",
        "couts_projet_gds": f"Cible {dscr:.2f}x" if dscr is not None else "Non disponible",
        "commentaires": "Le DSCR cible GDS n'est pas directement équivalent au DSCR minimum réalisé d'un projet pair."
    })
    rows.append({
        "cout": "Tarif / coût de l'énergie",
        "valeurs_standards": f"LCOE hydro IRENA: {standard_lcoe:.3f} USD/kWh" if standard_lcoe is not None else "Non disponible",
        "valeurs_projets_region": "Tarif hydro comparable non publié dans Sahofika",
        "couts_projet_gds": f"{tariff:.6f} {tariff_unit}" if isinstance(tariff, (int, float)) else "Non disponible",
        "commentaires": "La charge de capacité GDS et un LCOE énergétique ne sont pas directement comparables."
    })
    return rows
