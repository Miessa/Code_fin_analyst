# -*- coding: utf-8 -*-

"""
semantic_search.py

Recherche sémantique dans le catalogue de libellés.

Rôle :
    à partir d'un concept ARSEL et d'un catalogue complet,
    demander au LLM quels libellés méritent une inspection supplémentaire.

Le module ne choisit PAS la métrique finale.
Il retourne seulement de nouveaux candidats à examiner.
"""

import json


def _catalogue_reduit(catalogue):
    """
    Version compacte du catalogue envoyée au LLM.
    """

    resultat = []

    for i, c in enumerate(catalogue, start=1):
        resultat.append({
            "id": i,
            "cellule_libelle": c.get("cellule_libelle"),
            "libelle": c.get("libelle"),
            "adresse_valeur": c.get("adresse_valeur"),
            "valeur": c.get("valeur"),
        })

    return resultat


def construire_prompt_recherche(
    concept,
    catalogue,
    candidats_deja_vus=None,
    max_resultats=10,
):
    """
    Construit une demande de recherche sémantique.
    """

    deja_vus = {
        c.get("cellule_libelle")
        for c in (candidats_deja_vus or [])
    }

    concept_llm = {
        "cle": concept.get("cle"),
        "description": concept.get("description"),
        "definition": concept.get("definition"),
        "nature": concept.get("nature"),
        "famille_unite": concept.get("famille_unite"),
        "portee_temporelle": concept.get("portee_temporelle"),
        "semantique_positive": concept.get(
            "semantique_positive",
            []
        ),
        "semantique_negative": concept.get(
            "semantique_negative",
            []
        ),
    }

    catalogue_compact = _catalogue_reduit(catalogue)

    prompt = f"""
Tu explores un modèle financier Excel.

Le premier groupe de candidats n'était pas satisfaisant.
Tu dois rechercher dans le CATALOGUE COMPLET des libellés
qui pourraient réellement correspondre au concept métier.

CONCEPT :

{json.dumps(
    concept_llm,
    ensure_ascii=False,
    indent=2
)}

CELLULES DÉJÀ EXAMINÉES :

{json.dumps(
    sorted(deja_vus),
    ensure_ascii=False,
    indent=2
)}

CATALOGUE COMPLET :

{json.dumps(
    catalogue_compact,
    ensure_ascii=False,
    default=str
)}

Retourne au maximum {max_resultats} candidats.

IMPORTANT :

- cherche des synonymes et formulations métier équivalentes ;
- ne te limite pas aux mots exacts du concept ;
- distingue les concepts voisins ;
- évite les cellules déjà examinées ;
- privilégie les libellés pouvant représenter une hypothèse/input
  lorsque le concept recherché est une hypothèse ;
- n'invente aucune cellule ;
- utilise uniquement les id présents dans le catalogue.

Réponds UNIQUEMENT en JSON strict :

{{
  "ids": [12, 45, 901]
}}
"""

    return prompt.strip()


def rechercher_semantiquement(
    concept,
    catalogue,
    appeler_llm_json,
    candidats_deja_vus=None,
    max_resultats=10,
):
    """
    Retourne une liste d'entrées du catalogue.
    """

    if not catalogue:
        return []

    prompt = construire_prompt_recherche(
        concept=concept,
        catalogue=catalogue,
        candidats_deja_vus=candidats_deja_vus,
        max_resultats=max_resultats,
    )

    try:
        rep = appeler_llm_json(prompt)
    except Exception:
        return []

    if not isinstance(rep, dict):
        return []

    ids = rep.get("ids", [])

    if not isinstance(ids, list):
        return []

    resultat = []
    vus = set()

    for x in ids:
        try:
            idx = int(x)
        except Exception:
            continue

        if not (1 <= idx <= len(catalogue)):
            continue

        candidat = catalogue[idx - 1]

        adr = candidat.get("cellule_libelle")

        if adr in vus:
            continue

        vus.add(adr)
        resultat.append(candidat)

        if len(resultat) >= max_resultats:
            break

    return resultat