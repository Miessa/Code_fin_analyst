# -*- coding: utf-8 -*-
"""Rank-only fusion for retrieval systems whose raw scores are incomparable."""


def reciprocal_rank_fusion(ranked_lists, rrf_k=60):
    if rrf_k < 0:
        raise ValueError("rrf_k doit être positif ou nul")
    par_adresse = {}
    ordre = []
    for source, candidats in ranked_lists.items():
        for rang, candidat in enumerate(candidats or [], start=1):
            adresse = candidat.get("cellule_libelle")
            if not adresse:
                continue
            if adresse not in par_adresse:
                par_adresse[adresse] = {
                    **candidat,
                    "sources_retrieval": [],
                    "retrieval_ranks": {},
                    "score_rrf": 0.0,
                }
                ordre.append(adresse)
            fusionne = par_adresse[adresse]
            fusionne["sources_retrieval"].append(source)
            fusionne["retrieval_ranks"][source] = rang
            fusionne["score_rrf"] += 1.0 / (rrf_k + rang)
            for cle, valeur in candidat.items():
                if cle.startswith("score_") or cle in {
                    "penalites_semantiques", "embedding_model"
                }:
                    fusionne[cle] = valeur

    resultat = [par_adresse[adresse] for adresse in ordre]
    resultat.sort(key=lambda c: c["score_rrf"], reverse=True)
    maximum = resultat[0]["score_rrf"] if resultat else 0.0
    for candidat in resultat:
        candidat["score_rrf"] = round(candidat["score_rrf"], 8)
        candidat["score_rrf_normalise"] = round(
            candidat["score_rrf"] / maximum if maximum else 0.0, 6
        )
    return resultat
