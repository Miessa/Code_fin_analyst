# -*- coding: utf-8 -*-
"""LLM-assisted discovery of additional labels in the complete catalogue."""

import json


def _catalogue_reduit(catalogue):
    return [
        {
            "id": i,
            "cellule_libelle": candidat.get("cellule_libelle"),
            "libelle": candidat.get("libelle"),
            "adresse_valeur": candidat.get("adresse_valeur"),
            "valeur": candidat.get("valeur"),
        }
        for i, candidat in enumerate(catalogue, start=1)
    ]


def construire_prompt_recherche(concept, catalogue, candidats_deja_vus=None, max_resultats=10):
    deja_vus = {c.get("cellule_libelle") for c in (candidats_deja_vus or [])}
    concept_llm = {
        cle: concept.get(cle)
        for cle in (
            "cle", "description", "definition", "nature", "famille_unite",
            "portee_temporelle", "semantique_positive", "semantique_negative",
        )
    }
    concept_llm["semantique_positive"] = concept.get("semantique_positive", [])
    concept_llm["semantique_negative"] = concept.get("semantique_negative", [])
    return f"""
Tu explores un modèle financier Excel.

Le premier groupe de candidats n'était pas satisfaisant. Recherche dans le
CATALOGUE COMPLET les libellés pouvant correspondre au concept métier.

CONCEPT :
{json.dumps(concept_llm, ensure_ascii=False, indent=2)}

CELLULES DÉJÀ EXAMINÉES :
{json.dumps(sorted(deja_vus), ensure_ascii=False, indent=2)}

CATALOGUE COMPLET :
{json.dumps(_catalogue_reduit(catalogue), ensure_ascii=False, default=str)}

Retourne au maximum {max_resultats} candidats. Cherche des synonymes, distingue
les concepts voisins, évite les cellules déjà examinées et n'invente aucune
cellule. Utilise uniquement les id du catalogue.

Réponds UNIQUEMENT en JSON strict : {{"ids": [12, 45, 901]}}
""".strip()


def rechercher_semantiquement(concept, catalogue, appeler_llm_json,
                              candidats_deja_vus=None, max_resultats=10):
    if not catalogue:
        return []
    prompt = construire_prompt_recherche(
        concept, catalogue, candidats_deja_vus, max_resultats
    )
    try:
        reponse = appeler_llm_json(prompt)
    except Exception:
        return []
    if not isinstance(reponse, dict) or not isinstance(reponse.get("ids", []), list):
        return []

    resultat, vus = [], set()
    for valeur in reponse.get("ids", []):
        try:
            index = int(valeur)
        except (TypeError, ValueError):
            continue
        if not 1 <= index <= len(catalogue):
            continue
        candidat = catalogue[index - 1]
        adresse = candidat.get("cellule_libelle")
        if adresse in vus:
            continue
        vus.add(adresse)
        resultat.append(candidat)
        if len(resultat) >= max_resultats:
            break
    return resultat
