"""Build a deterministic financial opinion from metrics and benchmarks."""

from __future__ import annotations


SECTIONS = {
    "technique": {"puissance", "productible", "duree_construction", "duree_concession", "disponibilite"},
    "investissement": {"cout_construction", "investissement_total"},
    "exploitation": {"opex_1", "inflation_opex"},
    "financement_dette": {"gearing", "taux_dette", "duree_dette", "dscr_cible"},
    "fiscalite": {"is_taux", "tva", "wht", "amortissement_duree"},
    "rentabilite": {"tri_projet", "tri_fonds_propres", "wacc", "taux_actualisation"},
    "tarif": {"tarif"},
}


def _format_value(value, unit=None):
    if isinstance(value, float):
        rendered = f"{value:,.4g}".replace(",", " ")
    else:
        rendered = str(value)
    return f"{rendered} {unit}" if unit else rendered


def construire_analyse(registre, indicateurs, comparaisons):
    disponibles = {r.get("cle"): r for r in registre if r.get("valeur") is not None}
    manquantes = [r.get("cle") for r in registre if r.get("valeur") is None]
    sections = {}
    for section, keys in SECTIONS.items():
        constats = []
        absents = []
        for key in sorted(keys):
            item = disponibles.get(key)
            if item:
                constats.append(f"{item.get('description') or key}: {_format_value(item['valeur'], item.get('unite'))}.")
            else:
                absents.append(key)
        sections[section] = {"constats": constats, "points_attention":
                             [f"Donnée non disponible: {key}." for key in absents]}

    risques = []
    recommandations = []
    for comparison in comparaisons:
        key = comparison["indicator_key"]
        if (comparison["status"] == "COMPARED"
                and comparison.get("comparison_type") == "range"
                and comparison["verdict"] != "WITHIN"):
            risques.append(
                f"{key}: valeur {comparison['verdict'].lower()} par rapport à la référence "
                f"{comparison.get('source') or comparison['benchmark_key']}."
            )
            recommandations.append(f"Justifier l'écart de {key} et vérifier la comparabilité du périmètre.")
        elif comparison["status"] == "COMPARED" and comparison.get("comparison_type") == "point":
            recommandations.append(
                f"Interpréter l'écart de {key} par rapport au point de référence; "
                "un point moyen n'est pas une limite réglementaire."
            )
        elif comparison["status"] == "NOT_COMPARABLE":
            recommandations.append(
                f"Compléter le contexte de {key}: {', '.join(comparison['reasons'])}."
            )

    calcules = sum(i["calculable"] for i in indicateurs)
    compares = sum(c["status"] == "COMPARED" for c in comparaisons)
    synthese = (
        f"Phase 2 a traité {len(disponibles)} métriques validées, calculé {calcules} "
        f"indicateurs dérivés et réalisé {compares} comparaison(s) avec des références approuvées."
    )
    return {
        "synthese_executive": synthese,
        "sections": sections,
        "indicateurs_derives": indicateurs,
        "comparaisons_benchmark": comparaisons,
        "risques": list(dict.fromkeys(risques)),
        "donnees_manquantes_importantes": manquantes,
        "recommandations": list(dict.fromkeys(recommandations)),
    }


def generer_markdown(analyse):
    lines = ["# Analyse financière ARSEL — Phase 2\n\n",
             "## Synthèse exécutive\n\n", analyse["synthese_executive"] + "\n\n"]
    labels = {
        "technique": "Hypothèses techniques", "investissement": "Investissement",
        "exploitation": "Exploitation", "financement_dette": "Financement et dette",
        "fiscalite": "Fiscalité", "rentabilite": "Rentabilité", "tarif": "Tarif",
    }
    for key, title in labels.items():
        section = analyse["sections"][key]
        lines.extend([f"## {title}\n\n", "### Constats\n\n"])
        lines.extend(f"- {x}\n" for x in section["constats"] or ["Aucune donnée disponible."])
        lines.append("\n### Points d'attention\n\n")
        lines.extend(f"- {x}\n" for x in section["points_attention"] or ["Aucun point automatique."])
        lines.append("\n")

    lines.append("## Indicateurs dérivés\n\n| Indicateur | Valeur | Unité | Formule |\n|---|---:|---|---|\n")
    for item in analyse["indicateurs_derives"]:
        value = _format_value(item["valeur"]) if item["calculable"] else "Non calculable"
        lines.append(f"| {item['cle']} | {value} | {item['unite']} | {item['formule']} |\n")

    lines.append("\n## Comparaisons aux références\n\n| Indicateur | Valeur | Référence | Verdict | Source |\n|---|---:|---|---|---|\n")
    for item in analyse["comparaisons_benchmark"]:
        interval = (f"{item.get('target')} {item.get('unit') or ''}"
                    if item.get("comparison_type") == "point" else
                    f"{item.get('low')} – {item.get('high')} {item.get('unit') or ''}")
        verdict = item.get("verdict") or item["status"]
        lines.append(f"| {item['indicator_key']} | {item.get('value')} | {interval} | {verdict} | {item.get('source') or '—'} |\n")

    for title, key in (("Risques", "risques"), ("Données manquantes", "donnees_manquantes_importantes"),
                       ("Recommandations", "recommandations")):
        lines.append(f"\n## {title}\n\n")
        lines.extend(f"- {x}\n" for x in analyse[key] or ["Aucun élément automatique."])
    return "".join(lines)
