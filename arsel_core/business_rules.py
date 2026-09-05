# -*- coding: utf-8 -*-
"""Cheap deterministic business compatibility checks before final ranking."""

import re
import unicodedata


def _norm(value):
    value = unicodedata.normalize("NFD", str(value or "").lower())
    return " ".join(
        re.findall(r"[a-z0-9]+", "".join(
            c for c in value if unicodedata.category(c) != "Mn"
        ))
    )


RULES = {
    "tarif": {
        "required_any": ("tariff", "tarif", "capacity charge", "ppa", "selling price"),
        "excluded": ("revenue", "turnover", "payment amount"),
    },
    "taux_dette": {
        "required_any": ("interest rate", "cost of debt", "debt rate", "taux dette"),
        "excluded": ("interest expense", "interest amount", "interest paid"),
    },
    "duree_dette": {
        "required_any": ("loan tenor", "debt tenor", "maturity", "loan term"),
        "excluded": ("grace", "replacement", "tranche", "remaining maturity"),
    },
    "amortissement_duree": {
        "required_any": ("depreciation period", "useful life", "amortissement", "asset life"),
        "excluded": ("depreciation expense", "accumulated depreciation"),
    },
    "tri_fonds_propres": {
        "required_all_groups": (("irr", "tri"), ("equity", "sponsor", "shareholder", "fonds propres", "fp")),
        "excluded": ("project irr", "target irr"),
    },
    "wacc": {
        "required_any": ("wacc", "weighted average cost of capital", "cout moyen pondere"),
        "excluded": ("cost of debt", "cost of equity only"),
    },
    "productible": {
        "preferred": ("annual", "yearly", "year 1", "annuel", "12 months"),
        "excluded": ("3 months", "three months", "quarter", "quarterly", "monthly"),
    },
    "duree_construction": {
        "required_any": ("construction duration", "construction period", "length of construction"),
        "excluded": ("construction profile", "construction date", "months in construction"),
    },
    "duree_concession": {
        "required_any": ("concession period", "project life", "contract term", "length of operation", "operating period"),
        "excluded": ("debt", "grace", "replacement", "tranche", "maturity"),
    },
}


def evaluer_compatibilite(concept, candidat):
    """Return a factor in [0, 1] and explainable positive/negative signals."""
    cle = concept.get("cle")
    texte = _norm(" | ".join(str(candidat.get(k) or "") for k in (
        "libelle", "section", "contexte", "contexte_haut", "unite_detectee"
    )))
    valeur = candidat.get("valeur")
    positifs, negatifs = [], []
    if isinstance(valeur, (int, float)) and not isinstance(valeur, bool) and valeur == 0:
        return 0.0, positifs, ["valeur nulle considérée comme aberrante"]

    regle = RULES.get(cle, {})
    exclus = tuple(_norm(x) for x in regle.get("excluded", ()))
    trouves_exclus = [x for x in exclus if x and x in texte]
    if trouves_exclus:
        return 0.05, positifs, [f"périmètre exclu: {x}" for x in trouves_exclus]

    requis = tuple(_norm(x) for x in regle.get("required_any", ()))
    if requis:
        if any(x in texte for x in requis):
            positifs.append("libellé métier explicitement compatible")
        else:
            return 0.20, positifs, ["qualificateur métier obligatoire absent"]

    for groupe in regle.get("required_all_groups", ()):
        if not any(_norm(x) in texte for x in groupe):
            return 0.10, positifs, ["qualificateur métier obligatoire absent"]
    if regle.get("required_all_groups"):
        positifs.append("qualificateurs métier complets")

    preferes = tuple(_norm(x) for x in regle.get("preferred", ()))
    if preferes and any(x in texte for x in preferes):
        positifs.append("portée temporelle préférée")
        return 1.0, positifs, negatifs
    if preferes:
        negatifs.append("portée annuelle non démontrée")
        return 0.65, positifs, negatifs
    return 1.0, positifs, negatifs
