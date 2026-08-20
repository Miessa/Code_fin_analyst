# -*- coding: utf-8 -*-
"""Étapes déterministes partagées par l'extraction et les benchmarks."""

from .preselection import preselectionner
from .structure_detector import caracteriser
from .structure_filter import diagnostiquer
from .tfidf_search import fusionner_candidats
from .formula_dependency import concept_attend_agregat, calculer_boost_dependances


def valeur_plausible(valeur, borne_basse, borne_haute):
    return (
        isinstance(valeur, (int, float))
        and not isinstance(valeur, bool)
        and borne_basse <= abs(valeur) <= borne_haute
    )


def recuperer_candidats(
    concept, catalogue, index_tfidf, k_lexical=5, k_tfidf=30,
    index_dependances=None, pool_dependances=50,
):
    lexicaux = preselectionner(concept, catalogue, k=k_lexical)
    taille_pool = pool_dependances if (
        index_dependances is not None and concept_attend_agregat(concept)
    ) else k_tfidf
    tfidf = index_tfidf.rechercher(concept, k=taille_pool)
    for candidat in tfidf:
        analyse = {"dependency_count": 0, "leaf_count": 0,
                   "has_aggregate_formula": False, "max_depth_reached": 0}
        boost = 0.0
        if taille_pool > k_tfidf:
            analyse = index_dependances.analyser(candidat.get("adresse_valeur"))
            boost = calculer_boost_dependances(
                analyse, candidat.get("score_tfidf", 0.0)
            )
        candidat.update(analyse)
        candidat["dependency_boost"] = round(boost, 6)
        candidat["score_retrieval_final"] = round(
            candidat.get("score_tfidf", 0.0) + boost, 6
        )
    tfidf.sort(key=lambda c: c["score_retrieval_final"], reverse=True)
    tfidf = tfidf[:k_tfidf]
    return fusionner_candidats(lexicaux, tfidf), lexicaux, tfidf


def scorer_candidats(wb, concept, candidats, wb_formules=None):
    plage = concept.get("plage") or [float("-inf"), float("inf")]
    borne_basse, borne_haute = plage[0], plage[1]
    scored = []
    for candidat in candidats:
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
            score = diagnostic["score"]
            negatifs = list(diagnostic["signaux_negatifs"])
            if not valeur_plausible(candidat.get("valeur"), borne_basse, borne_haute):
                score *= 0.3
                negatifs.append("valeur hors plage plausible")
            scored.append({
                **candidat,
                "score": score,
                "diag": diag,
                "signaux_pos": diagnostic["signaux_positifs"],
                "signaux_neg": negatifs,
            })
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
