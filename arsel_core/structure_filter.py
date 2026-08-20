# -*- coding: utf-8 -*-
"""
structure_filter.py — CONFRONTE le diagnostic d'un candidat à l'ONTOLOGIE.

Répond UNIQUEMENT à : « la forme de ce candidat est-elle compatible avec ce que
l'ontologie demande ? » (le graphe de dépendances intervient dans une couche
ultérieure — pas ici).

Corrections clés :
  • SCORE NORMALISÉ par le poids réellement applicable -> scores comparables
    entre concepts (0..1 = niveau de compatibilité réel), quelles que soient les
    règles activées ;
  • 'unknown' produit de l'INCERTITUDE (score partiel), jamais une hypothèse ;
  • accès défensifs (.get) -> un candidat mal diagnostiqué ne casse pas la chaîne ;
  • is_total à trois états True / False / None (None = indéterminé) ;
  • séparation signaux_positifs / signaux_negatifs (pour le score explicable).
"""

POIDS = {
    "structure": 0.35,
    "nature": 0.20,
    "unite": 0.15,
    "selecteur": 0.15,
    "total": 0.15,
}

UNIT_ALIASES = {
    # taux / pourcentages
    "ratio": "percentage_rate",
    "percentage": "percentage_rate",
    "percentage_rate": "percentage_rate",

    # monnaie
    "currency": "currency_amount",
    "currency_amount": "currency_amount",

    # énergie
    "energy": "energy",

    # puissance
    "power": "power",

    # durée
    "duration": "duration",

    # inconnu
    "unknown": "unknown",
}

MAP_NATURE = {"amount": "montant", "rate": "taux", "integer": "montant"}

def _normaliser_unite(unite):
    if not unite:
        return "unknown"

    return UNIT_ALIASES.get(
        unite,
        unite
    )

def _nature_candidat(diag):
    return MAP_NATURE.get(diag.get("value_type"), "unknown")


def diagnostiquer(diag, concept):
    """Rapport lisible + score NORMALISÉ (0..1). concept = entrée d'ontologie."""
    lignes, positifs, negatifs = [], [], []
    score = 0.0
    poids_actif = 0.0

    # 1) STRUCTURE (toujours évaluée)
    struct = diag.get("structure", "unknown")
    pref = concept.get("structure_preferee", [])
    acc = concept.get("structure_acceptee", [])
    pen = concept.get("structures_penalisees", [])
    poids_actif += POIDS["structure"]
    if struct in pref:
        pts, verdict = POIDS["structure"], "OK (préférée)"
        positifs.append(f"structure {struct} préférée")
    elif struct in acc:
        pts, verdict = POIDS["structure"] * 0.6, "OK (acceptée)"
        positifs.append(f"structure {struct} acceptable")
    elif struct in pen:
        pts, verdict = 0.0, "déclassée"
        negatifs.append(f"structure {struct} pénalisée")
    else:
        pts, verdict = POIDS["structure"] * 0.3, "incertain"
    score += pts
    lignes.append(f"Structure: {struct}  attendu: {pref or '?'}  → {verdict}")

    # 2) NATURE (seulement si le concept la précise)
    nat_attendu = concept.get("nature")
    if nat_attendu:
        poids_actif += POIDS["nature"]
        nat_c = _nature_candidat(diag)
        if nat_c == nat_attendu:
            pts, verdict = POIDS["nature"], "OK"
            positifs.append(f"nature {nat_c} compatible")
        elif nat_c == "unknown":
            pts, verdict = POIDS["nature"] * 0.3, "incertain"
        else:
            pts, verdict = 0.0, "incompatible"
            negatifs.append(f"nature {nat_c} ≠ {nat_attendu}")
        score += pts
        lignes.append(f"Nature: {nat_c}  attendu: {nat_attendu}  → {verdict}")

    
    # 3) UNITÉ
    uf_brut = diag.get(
        "unit_family",
        "unknown"
    )

    uf_attendu_brut = concept.get(
        "famille_unite"
    )

    if uf_attendu_brut:

        poids_actif += POIDS["unite"]

        # Normalisation vers une taxonomie commune
        uf = _normaliser_unite(
            uf_brut
        )

        uf_attendu = _normaliser_unite(
            uf_attendu_brut
        )

        if uf == uf_attendu:

            verdict = "OK"
            pts = POIDS["unite"]

            positifs.append(
                f"unité {uf_brut} compatible"
            )

        elif uf == "unknown":

            verdict = "incertain"
            pts = POIDS["unite"] * 0.5

            negatifs.append(
                "famille d'unité détectée avec faible confiance"
            )

        else:

            verdict = "incompatible"
            pts = 0.0

            negatifs.append(
                f"unité {uf_brut} ≠ {uf_attendu_brut}"
            )

        score += pts

        lignes.append(
            f"Unité: {uf_brut} "
            f"attendu: {uf_attendu_brut} "
            f"→ {verdict}"
        )

    val = concept.get("validation", {})
    # 4) SÉLECTEUR (si la règle est active)
    if val.get("rejeter_selecteur"):
        poids_actif += POIDS["selecteur"]
        is_sel = diag.get("is_selector", False)
        if is_sel is True:
            pts, verdict = 0.0, "déclassé (sélecteur)"
            negatifs.append("candidat = sélecteur (rejeté)")
        elif is_sel is None:
            pts, verdict = POIDS["selecteur"] * 0.4, "indéterminé"
        else:
            pts, verdict = POIDS["selecteur"], "OK"
            positifs.append("n'est pas un sélecteur")
        score += pts
        lignes.append(f"Sélecteur: {is_sel}  → {verdict}")

    # 5) TOTAL attendu (si la règle est active) — trois états True/False/None
    if val.get("preferer_total"):
        poids_actif += POIDS["total"]
        is_tot = diag.get("is_total", None)
        if is_tot is True:
            pts, verdict = POIDS["total"], "OK"
            positifs.append("total détecté")
        elif is_tot is None:
            pts, verdict = POIDS["total"] * 0.4, "indéterminé"
        else:
            pts, verdict = 0.0, "total attendu, non détecté"
            negatifs.append("total attendu, non détecté")
        score += pts
        lignes.append(f"Total détecté: {is_tot}  attendu: true  → {verdict}")

    # 6) série alors qu'un total est attendu (signal négatif fort, hors score direct)
    if val.get("rejeter_serie_si_total_existe") and diag.get("is_time_series") and not diag.get("is_total"):
        negatifs.append("série temporelle alors qu'un total est attendu")
        lignes.append("Série temporelle sans total  → signal négatif")

    score_final = score / poids_actif if poids_actif > 0 else 0.0
    return {
        "score": round(score_final, 3),
        "signaux_positifs": positifs,
        "signaux_negatifs": negatifs,
        "rapport": lignes,
    }


def scorer(diag, concept):
    """(score normalisé, signaux_negatifs) pour classer/filtrer les candidats."""
    d = diagnostiquer(diag, concept)
    return d["score"], d["signaux_negatifs"]
