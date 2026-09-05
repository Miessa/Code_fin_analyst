# -*- coding: utf-8 -*-
"""Étapes déterministes partagées par l'extraction et les benchmarks."""

from .preselection import preselectionner
from .structure_detector import caracteriser
from .structure_filter import diagnostiquer
from .rank_fusion import reciprocal_rank_fusion
from .formula_dependency import concept_attend_agregat, calculer_boost_dependances
from .business_rules import evaluer_compatibilite


def valeur_plausible(valeur, borne_basse, borne_haute):
    return (
        isinstance(valeur, (int, float))
        and not isinstance(valeur, bool)
        and borne_basse <= abs(valeur) <= borne_haute
    )


def recuperer_candidats(
    concept, catalogue, index_tfidf, k_lexical=5, k_tfidf=30,
    index_dependances=None, pool_dependances=50, index_embeddings=None,
    k_embeddings=20, rrf_k=60,
):
    lexicaux = preselectionner(concept, catalogue, k=k_lexical)
    taille_pool = pool_dependances if (
        index_dependances is not None and concept_attend_agregat(concept)
    ) else k_tfidf
    tfidf = index_tfidf.rechercher(concept, k=taille_pool)
    embeddings = (
        index_embeddings.rechercher(concept, k=k_embeddings)
        if index_embeddings is not None else []
    )
    fusionnes = reciprocal_rank_fusion(
        {"lexical": lexicaux, "tfidf": tfidf, "embeddings": embeddings},
        rrf_k=rrf_k,
    )
    for candidat in fusionnes:
        analyse = {"dependency_count": 0, "leaf_count": 0,
                   "has_aggregate_formula": False, "max_depth_reached": 0}
        boost = 0.0
        if index_dependances is not None and concept_attend_agregat(concept):
            analyse = index_dependances.analyser(candidat.get("adresse_valeur"))
            boost = calculer_boost_dependances(
                analyse, candidat.get("score_rrf_normalise", 0.0)
            )
        candidat.update(analyse)
        candidat["dependency_boost"] = round(boost, 6)
        candidat["score_retrieval_final"] = round(
            candidat.get("score_rrf_normalise", 0.0) + boost, 6
        )
    fusionnes.sort(key=lambda c: c["score_retrieval_final"], reverse=True)
    return fusionnes[:k_tfidf], lexicaux, tfidf


def scorer_candidats(wb, concept, candidats, wb_formules=None):
    plage = concept.get("plage") or [float("-inf"), float("inf")]
    borne_basse, borne_haute = plage[0], plage[1]
    scored = []
    for candidat in candidats:
        facteur_metier, positifs_metier, negatifs_metier = evaluer_compatibilite(
            concept, candidat
        )
        # Hard business incompatibilities are cheap to detect and must not
        # trigger costly dispersed workbook/series inspection.
        if facteur_metier < 0.5:
            scored.append({
                **candidat,
                "score": 0.0,
                "score_structure": None,
                "score_metier": facteur_metier,
                "diag": None,
                "signaux_pos": positifs_metier,
                "signaux_neg": negatifs_metier,
            })
            continue
        try:
            diag = caracteriser(
                wb,
                candidat["cellule_libelle"],
                candidat["adresse_valeur"],
                wb_formules=wb_formules,
            )
            # Une cellule de synthèse peut n'être qu'un lien vers une formule
            # d'agrégation située quelques cellules plus loin. L'analyse de
            # dépendances a déjà établi cette preuve : elle doit compter dans
            # le diagnostic structurel, sinon un libellé court comme "EPC" est
            # injustement classé comme simple scalaire.
            if (
                candidat.get("has_aggregate_formula")
                and diag.get("structure") == "scalar"
            ):
                diag["structure"] = "scalar_aggregate"
                diag["is_total"] = True
            diagnostic = diagnostiquer(diag, concept)
            score = diagnostic["score"] * facteur_metier
            negatifs = list(diagnostic["signaux_negatifs"])
            negatifs.extend(negatifs_metier)
            if not valeur_plausible(candidat.get("valeur"), borne_basse, borne_haute):
                score *= 0.3
                negatifs.append("valeur hors plage plausible")
            scored.append({
                **candidat,
                "score": score,
                "diag": diag,
                "signaux_pos": diagnostic["signaux_positifs"],
                "score_structure": diagnostic["score"],
                "score_metier": facteur_metier,
                "signaux_neg": negatifs,
            })
            scored[-1]["signaux_pos"].extend(positifs_metier)
        except Exception as ex:
            scored.append({
                **candidat,
                "score": 0.0,
                "diag": None,
                "signaux_pos": [],
                "signaux_neg": [f"diagnostic échoué : {type(ex).__name__}: {ex}"],
            })
    scored.sort(
        key=lambda candidat: (
            candidat["score"],
            -candidat.get("penalites_semantiques", 0),
            candidat.get("score_retrieval_final", 0.0),
        ),
        reverse=True,
    )
    return scored
