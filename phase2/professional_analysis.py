"""Deterministic, regulator-oriented financial opinion."""

LABELS = {
    "taux_dette": "Taux de dette", "wacc": "WACC",
    "cout_construction": "Coût de construction", "investissement_total": "Investissement total",
}


def _idx(xs): return {x["cle"]: x for x in xs}
def _v(xs, key): return (xs.get(key) or {}).get("valeur")
def _pct(x, n=1):
    return f"{100*x:.{n}f} %" if isinstance(x, (int, float)) else None


def _num(x, n=0):
    return f"{x:,.{n}f}".replace(",", " ") if isinstance(x, (int, float)) else None
def _sec(facts, attention):
    return {"constats": [x for x in facts if x], "points_attention": [x for x in attention if x]}


def _rate_fact(name, value):
    if isinstance(value, (int, float)):
        return f"{name} : {_pct(value, 2)}."
    if isinstance(value, list) and value:
        return f"{name} : {' | '.join(str(x) for x in value)}."
    if isinstance(value, str) and value.strip():
        return f"{name} : {value}."
    return None


def construire_analyse(registre, indicateurs, comparaisons):
    r, d = _idx(registre), _idx(indicateurs)
    v, q = lambda k: _v(r, k), lambda k: _v(d, k)
    currency = (r.get("cout_construction") or {}).get("unite") or ""
    capex, total, opex = v("cout_construction"), v("investissement_total"), v("opex_1")
    cshare, other = q("construction_share"), q("non_construction_share")
    debt, equity, cf = q("debt_share"), q("equity_share"), q("capacity_factor")
    spread, premium, tail = q("project_irr_spread"), q("equity_irr_premium"), q("debt_tail")
    capex_mw, opex_ratio = q("capex_per_mw"), q("opex_to_capex")

    inflation = v("inflation_opex")
    inflation_facts = []
    if isinstance(inflation, list):
        inflation_facts = [f"Trajectoire d'indexation OPEX : {x}." for x in inflation]

    sections = {
        "technique": _sec([
            f"Puissance installée : {_num(v('puissance'))} MW." if v("puissance") is not None else None,
            f"Productible annuel : {_num(v('productible'))} MWh/an." if v("productible") is not None else None,
            f"Facteur de charge implicite : {_pct(cf)}." if cf is not None else None,
            _rate_fact("Disponibilité", v("disponibilite")),
            f"Construction : {_num(v('duree_construction'))} mois." if v("duree_construction") is not None else None,
            f"Concession : {_num(v('duree_concession'))} ans." if v("duree_concession") is not None else None,
        ], ["Une durée de construction supérieure à cinq ans accroît l'exposition aux retards, surcoûts et intérêts intercalaires."
            if (v("duree_construction") or 0) > 60 else None]),
        "investissement": _sec([
            f"Coût de construction : {_num(capex)} {currency}." if capex is not None else None,
            f"Investissement total : {_num(total)} {currency}." if total is not None else None,
            f"La construction représente {_pct(cshare)} du total." if cshare is not None else None,
            f"Les coûts hors construction représentent {_pct(other)} du total." if other is not None else None,
            f"CAPEX normalisé : {_num(capex_mw)} USD/MW." if capex_mw is not None else None,
        ], ["La part des coûts hors construction est élevée; demander une décomposition complète des coûts de développement, impôts et financement."
            if other is not None and other > .30 else None,
            "Le CAPEX/MW en USD reste indisponible sans taux de change approuvé." if capex_mw is None else None]),
        "exploitation": _sec([
            f"OPEX de première année : {_num(opex)} {currency}/an." if opex is not None else None,
            f"OPEX initial / coût de construction : {_pct(opex_ratio)} par an." if opex_ratio is not None else None,
            *inflation_facts,
        ], ["Vérifier que l'indexation contractuelle du tarif couvre la trajectoire d'inflation des OPEX." if inflation else None]),
        "financement_dette": _sec([
            f"Financement : {_pct(debt)} de dette et {_pct(equity)} de fonds propres." if debt is not None else None,
            f"DSCR cible : {v('dscr_cible'):.2f}x." if v("dscr_cible") is not None else None,
            f"Maturité de la dette : {_num(v('duree_dette'))} ans." if v("duree_dette") is not None else None,
            f"La dette expire {tail:.0f} ans avant la concession." if tail is not None else None,
            _rate_fact("Taux de dette", v("taux_dette")),
        ], ["Le taux de dette manque; le service de la dette ne peut pas être apprécié complètement." if v("taux_dette") is None else None,
            "Un gearing de 75 % augmente la sensibilité aux retards, surcoûts et sous-performance." if debt is not None and debt >= .75 else None]),
        "fiscalite": _sec([
            _rate_fact("Impôt sur les sociétés", v("is_taux")), _rate_fact("TVA", v("tva")),
            _rate_fact("Retenue à la source", v("wht")),
            f"Amortissement comptable : {_num(v('amortissement_duree'))} ans." if v("amortissement_duree") is not None else None,
        ], ["Confirmer la récupération de TVA et l'assiette de la retenue à la source dans les contrats."]),
        "rentabilite": _sec([
            _rate_fact("TRI projet", v("tri_projet")), _rate_fact("TRI fonds propres", v("tri_fonds_propres")),
            _rate_fact("Taux d'actualisation", v("taux_actualisation")), _rate_fact("WACC", v("wacc")),
            f"Le TRI projet dépasse le taux d'actualisation de {_pct(spread, 2)}." if spread is not None else None,
            f"La prime du TRI fonds propres sur le TRI projet est de {_pct(premium, 2)}." if premium is not None else None,
        ], ["L'absence de WACC empêche une conclusion formelle sur la création de valeur." if v("wacc") is None else None,
            "La prime de rendement des fonds propres paraît limitée au regard du levier financier."
            if premium is not None and premium < .02 and debt is not None and debt >= .70 else None]),
        "tarif": _sec([
            f"Charge de capacité : {v('tarif'):.6f} {(r.get('tarif') or {}).get('unite')}." if v("tarif") is not None else None,
        ], ["Une charge de capacité en EUR/kW/mois ne doit pas être comparée directement à un prix d'énergie en EUR/kWh."]),
    }

    applied = [x for x in comparaisons if x.get("status") == "COMPARED"]
    excluded = [x for x in comparaisons if x.get("status") != "COMPARED"]
    irena_cf = next((x for x in applied if x.get("benchmark_key") ==
                     "irena_2024_hydropower_capacity_factor"), None)
    if irena_cf:
        sections["technique"]["constats"].append(
            f"Le facteur de charge du projet ({_pct(irena_cf['value'])}) est supérieur au point de référence mondial IRENA 2024 ({_pct(irena_cf['target'])})."
        )
        sections["technique"]["points_attention"].append(
            "Cet écart favorable doit être corroboré par les études hydrologiques; la moyenne IRENA n'est pas une limite réglementaire."
        )
    risks = []
    if other is not None and other > .30: risks.append(f"Coûts hors construction élevés ({_pct(other)} du total).")
    if debt is not None and debt >= .75: risks.append(f"Levier financier élevé ({_pct(debt)} de dette).")
    if v("wacc") is None or v("taux_dette") is None: risks.append("Coût du capital incomplet: WACC et/ou taux de dette indisponibles.")

    dscr_text = f", avec un DSCR cible de {v('dscr_cible'):.2f}x" if v("dscr_cible") is not None else ""
    summary_parts = []
    if total is not None:
        investment = f"L'investissement total atteint {_num(total)} {currency}."
        if cshare is not None:
            investment = (
                f"L'investissement total atteint {_num(total)} {currency}, dont "
                f"{_pct(cshare)} correspond aux travaux de construction."
            )
        elif capex is None:
            investment += " Le coût de construction n'étant pas validé, sa part ne peut pas être calculée."
        summary_parts.append(investment)
    if debt is not None:
        summary_parts.append(f"La structure financière est fortement endettée ({_pct(debt)}{dscr_text}).")
    if v("tri_projet") is not None and v("taux_actualisation") is not None:
        summary_parts.append(
            f"Le TRI projet de {_pct(v('tri_projet'), 2)} dépasse le taux "
            f"d'actualisation de {_pct(v('taux_actualisation'), 2)}."
        )
    if v("wacc") is None or v("taux_dette") is None:
        summary_parts.append(
            "Le coût du capital reste incomplet : le WACC et/ou le taux de dette sont indisponibles."
        )
    summary_parts.append(
        "Les priorités de revue sont la justification des coûts, les conditions de dette et la cohérence entre tarif et OPEX."
    )
    summary = " ".join(summary_parts)
    return {
        "synthese_executive": summary, "sections": sections, "indicateurs_derives": indicateurs,
        "comparaisons_benchmark": applied, "comparaisons_non_appliquees": excluded,
        "risques": risks, "donnees_manquantes_importantes": [LABELS[k] for k in ("taux_dette", "wacc") if v(k) is None],
        "recommandations": [
            "Obtenir la décomposition complète de l'investissement total et la rapprocher du coût EPC.",
            "Documenter le taux de dette, le WACC et les conditions de refinancement.",
            "Tester le DSCR et les TRI sous des scénarios de retard, dépassement de CAPEX et baisse du productible.",
            "Vérifier l'adéquation entre indexation tarifaire et inflation des OPEX.",
        ],
    }


def generer_markdown(a):
    out = ["# Analyse financière ARSEL — Phase 2\n\n", "## Synthèse exécutive\n\n", a["synthese_executive"] + "\n\n"]
    titles = {"technique": "Hypothèses techniques", "investissement": "Investissement", "exploitation": "Exploitation",
              "financement_dette": "Financement et dette", "fiscalite": "Fiscalité", "rentabilite": "Rentabilité", "tarif": "Tarif"}
    for key, title in titles.items():
        s = a["sections"][key]; out += [f"## {title}\n\n"] + [f"- {x}\n" for x in s["constats"]]
        if s["points_attention"]: out += ["\n### Points d'attention\n\n"] + [f"- {x}\n" for x in s["points_attention"]]
        out.append("\n")
    out.append("## Indicateurs financiers dérivés\n\n| Indicateur | Valeur | Unité |\n|---|---:|---|\n")
    for x in a["indicateurs_derives"]:
        if x["calculable"]:
            val = _pct(x["valeur"], 2) if x["unite"].startswith("ratio") else _num(x["valeur"], 2)
            out.append(f"| {x['cle']} | {val} | {x['unite']} |\n")
    out.append("\n## Tableau de comparaison des benchmarks\n\n")
    out.append("| Coûts | Valeurs standards | Valeurs pour des projets en cours de développement dans la région | Coûts du projet analysé | Commentaires |\n")
    out.append("|---|---|---|---|---|\n")
    for row in a.get("tableau_benchmark_detaille", []):
        out.append(
            f"| {row['cout']} | {row['valeurs_standards']} | "
            f"{row['valeurs_projets_region']} | {row['couts_projet_gds']} | "
            f"{row['commentaires']} |\n"
        )
    sector = a.get("comparaison_sectorielle_irena", {})
    out.append("\n### Références sectorielles IRENA issues de la base active\n\n")
    if sector.get("status") != "APPLIED":
        out.append(f"Références non appliquées : {sector.get('reason', 'aucune référence compatible')}.\n")
    else:
        out.append("| Métrique | Référence | Unité | Géographie | Position du projet | Provenance |\n")
        out.append("|---|---:|---|---|---|---|\n")
        for item in sector.get("comparisons", []):
            out.append(f"| {item['metric']} | {item.get('value')} | {item.get('unit')} | "
                       f"{item.get('geography')} | {item.get('position')} | {item.get('source_location')} |\n")
    peers = a.get("comparaison_projets_pairs", {})
    out.append("\n## Projets comparables approuvés\n\n")
    if peers.get("status") != "APPLIED":
        out.append("Comparaison par projets pairs non réalisée ou aucun comparable approuvé.\n")
    else:
        out.append(f"Comparables approuvés : {peers.get('approved_count', 0)}.\n\n")
        for item in peers.get("approved_projects", []):
            out.append(f"- {item.get('project_name')} — score {item.get('score', 0):.1%}\n")
        out.append("\n| Métrique | Projet | P25 | Médiane | P75 | n | Position | Fiabilité |\n")
        out.append("|---|---:|---:|---:|---:|---:|---|---|\n")
        for item in peers.get("comparisons", []):
            out.append(
                f"| {item['label']} | {item.get('project_value')} | {item.get('p25')} | "
                f"{item.get('median')} | {item.get('p75')} | {item.get('sample_size')} | "
                f"{item.get('position')} | {item.get('reliability')} |\n"
            )
    out.append("\n## Contrôles et points de référence appliqués\n\n")
    if not a["comparaisons_benchmark"]: out.append("Aucune comparaison externe applicable et calculable avec le contexte validé.\n")
    else:
        out.append("| Indicateur | Projet | Référence | Position | Source |\n|---|---:|---:|---|---|\n")
        for x in a["comparaisons_benchmark"]:
            if x.get("comparison_type") == "point":
                ref = x.get("target")
            elif x.get("low") is None:
                ref = f"≤ {x.get('high')}"
            elif x.get("high") is None:
                ref = f"≥ {x.get('low')}"
            else:
                ref = f"{x.get('low')}–{x.get('high')}"
            src = f"[{x['source']}]({x['source_url']})" if x.get("source_url") else x.get("source", "—")
            out.append(f"| {x['indicator_key']} | {x['value']:.4g} | {ref} {x['unit']} | {x['verdict']} | {src} |\n")
    for title, key in (("Risques principaux", "risques"), ("Données manquantes importantes", "donnees_manquantes_importantes"), ("Recommandations", "recommandations")):
        out += [f"\n## {title}\n\n"] + [f"- {x}\n" for x in a[key]]
    return "".join(out)
