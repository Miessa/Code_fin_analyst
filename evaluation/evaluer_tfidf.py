# -*- coding: utf-8 -*-
"""Évalue le retrieval TF-IDF contre des cellules validées par un analyste.

Usage :
    python evaluer_tfidf.py MODELE.xlsm hypotheses_validees.json

Le registre utilise le format produit par ``arsel_analyse.etape3``. Une entrée
peut aussi fournir ``adresses`` (liste) lorsqu'il existe plusieurs cellules
acceptables pour un même concept. Aucune cellule n'est déduite d'une valeur :
seules les adresses explicitement validées constituent la vérité terrain.
"""

import argparse
import json
import os
import sys

from arsel_core.collecter_libelles import collecter
from arsel_core.tfidf_search import IndexTfidf


K_DEFAUT = (5, 10, 20)


def charger_json(chemin):
    if not os.path.exists(chemin):
        raise FileNotFoundError(f"Fichier introuvable : {chemin}")
    with open(chemin, encoding="utf-8") as fichier:
        return json.load(fichier)


def charger_concepts(chemin):
    document = charger_json(chemin)
    entrees = document.get("entrees", []) if isinstance(document, dict) else []
    return {entree["cle"]: entree for entree in entrees if entree.get("cle")}


def _adresses_verite(entree):
    adresses = entree.get("label_addresses")
    if adresses is None:
        adresses = entree.get("adresses")
    if adresses is None:
        adresses = [entree.get("adresse")]
    elif isinstance(adresses, str):
        adresses = [adresses]

    # Les vérités terrain complexes peuvent décrire plusieurs séries, chacune
    # avec sa propre cellule de libellé.
    adresses = list(adresses or [])
    for serie in entree.get("series", []) or []:
        if serie.get("label_address"):
            adresses.append(serie["label_address"])
    return {str(adresse) for adresse in adresses if adresse}


def normaliser_registre(document):
    """Accepte un registre et le format enrichi ``ground_truth_kikot``."""

    if isinstance(document, list):
        return document
    if isinstance(document, dict) and isinstance(document.get("metrics"), dict):
        return [
            {"cle": cle, **(contenu or {})}
            for cle, contenu in document["metrics"].items()
        ]
    raise ValueError(
        "La vérité terrain doit être une liste ou contenir un objet 'metrics'."
    )


def evaluer(index, concepts, registre, ks=K_DEFAUT):
    """Calcule les rangs, Recall@K et MRR pour les entrées évaluables."""

    ks = tuple(sorted({int(k) for k in ks if int(k) > 0}))
    if not ks:
        raise ValueError("Au moins une valeur positive de K est requise.")
    registre = normaliser_registre(registre)

    details = []
    ignores = []
    for entree in registre:
        cle = entree.get("cle")
        if entree.get("evaluation_enabled") is False:
            ignores.append({"cle": cle, "raison": "évaluation désactivée"})
            continue
        verite = _adresses_verite(entree)
        if not cle or not verite:
            ignores.append({"cle": cle, "raison": "adresse validée absente"})
            continue
        concept = concepts.get(cle)
        if concept is None:
            ignores.append({"cle": cle, "raison": "concept absent du référentiel"})
            continue

        resultats = index.rechercher(concept, k=len(index.catalogue))
        rang = next(
            (
                position
                for position, candidat in enumerate(resultats, start=1)
                if candidat.get("cellule_libelle") in verite
            ),
            None,
        )
        details.append(
            {
                "cle": cle,
                "adresses_attendues": sorted(verite),
                "rang": rang,
                "trouve": rang is not None,
                "score": (
                    resultats[rang - 1].get("score_tfidf")
                    if rang is not None
                    else None
                ),
                "top1": (
                    resultats[0].get("cellule_libelle") if resultats else None
                ),
                "top1_libelle": resultats[0].get("libelle") if resultats else None,
            }
        )

    total = len(details)
    rappels = {
        f"recall@{k}": (
            sum(d["rang"] is not None and d["rang"] <= k for d in details)
            / total
            if total
            else None
        )
        for k in ks
    }
    mrr = (
        sum(1.0 / d["rang"] for d in details if d["rang"] is not None) / total
        if total
        else None
    )
    return {
        "nombre_evalue": total,
        "nombre_ignore": len(ignores),
        **rappels,
        "mrr": mrr,
        "details": details,
        "ignores": ignores,
    }


def afficher(rapport):
    if rapport["nombre_evalue"] == 0:
        print(
            "Aucune métrique évaluable : ajoutez au registre au moins une "
            "entrée avec 'cle' et 'adresse' validées par un analyste."
        )
        if rapport["nombre_ignore"]:
            print(f"Entrées ignorées : {rapport['nombre_ignore']}")
        return

    print("\nRésultats TF-IDF")
    print("-" * 72)
    print(f"Métriques évaluées : {rapport['nombre_evalue']}")
    for cle, valeur in rapport.items():
        if cle.startswith("recall@"):
            print(f"{cle.capitalize():12s}: {valeur:.1%}")
    print(f"MRR         : {rapport['mrr']:.3f}\n")
    print(f"{'Métrique':24s} {'Rang':>6s}  {'Top 1'}")
    print("-" * 72)
    for detail in rapport["details"]:
        rang = str(detail["rang"]) if detail["rang"] is not None else "—"
        print(f"{detail['cle'][:24]:24s} {rang:>6s}  {detail['top1'] or '—'}")


def analyser_arguments(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("modele", help="Classeur Excel .xlsm à indexer")
    parser.add_argument(
        "registre",
        nargs="?",
        default="hypotheses_validees.json",
        help="Registre des cellules validées",
    )
    parser.add_argument(
        "--referentiel",
        default="data/referentiel_arsel.json",
        help="Référentiel des concepts ARSEL",
    )
    parser.add_argument("--sortie-json", help="Chemin facultatif du rapport JSON")
    return parser.parse_args(argv)


def main(argv=None):
    args = analyser_arguments(argv)
    concepts = charger_concepts(args.referentiel)
    registre = charger_json(args.registre)

    print(f"Collecte du catalogue : {args.modele}")
    catalogue = collecter(args.modele)
    print(f"Libellés indexés : {len(catalogue)}")
    rapport = evaluer(IndexTfidf(catalogue), concepts, registre)
    afficher(rapport)

    if args.sortie_json:
        with open(args.sortie_json, "w", encoding="utf-8") as fichier:
            json.dump(rapport, fichier, ensure_ascii=False, indent=2)
        print(f"Rapport JSON : {args.sortie_json}")

    return 0 if rapport["nombre_evalue"] else 2


if __name__ == "__main__":
    sys.exit(main())
