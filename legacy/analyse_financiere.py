# -*- coding: utf-8 -*-

"""
analyse_financiere.py

Analyse financière ARSEL à partir des hypothèses
VALIDÉES par l'analyste.

Entrée :
    hypotheses_validees.json

Sorties :
    analyse_financiere.json
    analyse_financiere.md

IMPORTANT :
    Ce module ne lit PAS Excel.
    Il travaille uniquement à partir du registre validé.
"""

import json
import os
import sys

from arsel_core.gemini_provider import appeler_json


FICHIER_DEFAUT = "hypotheses_validees.json"


# ==========================================================
# 1. Chargement du registre
# ==========================================================

def charger_registre(chemin):

    if not os.path.exists(chemin):
        raise FileNotFoundError(
            f"Registre introuvable : {chemin}"
        )

    with open(
        chemin,
        "r",
        encoding="utf-8"
    ) as f:

        registre = json.load(f)

    if not isinstance(registre, list):
        raise ValueError(
            "Le registre doit être une liste JSON."
        )

    return registre


# ==========================================================
# 2. Indexation par clé métier
# ==========================================================

def indexer_registre(registre):

    return {
        r.get("cle"): r
        for r in registre
        if r.get("cle")
    }


# ==========================================================
# 3. Identifier données disponibles / indisponibles
# ==========================================================

def separer_disponibilite(registre):

    disponibles = []
    indisponibles = []

    for r in registre:

        if r.get("valeur") is None:
            indisponibles.append(r)

        else:
            disponibles.append(r)

    return disponibles, indisponibles


# ==========================================================
# 4. Construction du prompt ARSEL
# ==========================================================

def construire_prompt(registre):

    disponibles, indisponibles = (
        separer_disponibilite(registre)
    )

    donnees = [
        {
            "cle": r.get("cle"),
            "description": r.get("description"),
            "categorie": r.get("categorie"),
            "valeur": r.get("valeur"),
            "nature": r.get("nature"),
            "source": r.get("source"),
            "statut": r.get("statut"),
        }
        for r in disponibles
    ]

    manquantes = [
        {
            "cle": r.get("cle"),
            "description": r.get("description"),
        }
        for r in indisponibles
    ]

    prompt = f"""
Tu es un analyste financier spécialisé dans les projets
d'infrastructure et d'énergie soumis à une revue réglementaire.

Tu dois produire une analyse financière structurée à partir
UNIQUEMENT des hypothèses validées ci-dessous.

IMPORTANT :

1. N'invente JAMAIS une valeur absente.
2. Ne remplace jamais une donnée indisponible par une estimation.
3. Distingue :
   - constat factuel ;
   - interprétation financière ;
   - risque ;
   - recommandation.
4. Si les données ne permettent pas une conclusion, indique-le.
5. Ne présente pas une extraction automatique comme une vérité
   absolue : les valeurs ont été validées par un analyste.
6. N'utilise aucun benchmark externe non fourni.
7. Ne suppose aucune norme réglementaire précise qui n'est pas
   fournie.
8. Analyse les relations ENTRE les métriques lorsqu'elles sont
   disponibles.

DONNÉES VALIDÉES :

{json.dumps(
    donnees,
    ensure_ascii=False,
    indent=2,
    default=str
)}

DONNÉES NON DISPONIBLES :

{json.dumps(
    manquantes,
    ensure_ascii=False,
    indent=2
)}

L'analyse doit suivre cette logique :

A. SYNTHÈSE EXÉCUTIVE
Résumer la situation financière générale du projet.

B. HYPOTHÈSES TECHNIQUES
Examiner lorsque disponibles :
- puissance ;
- productible ;
- disponibilité ;
- durée de construction ;
- durée de concession.

C. INVESTISSEMENT
Examiner :
- coût de construction ;
- investissement total ;
- cohérence entre les deux ;
- poids apparent des coûts hors construction.

D. EXPLOITATION
Examiner :
- OPEX première année ;
- inflation OPEX ;
- soutenabilité des charges d'exploitation.

E. FINANCEMENT ET DETTE
Examiner :
- gearing ;
- taux de dette ;
- durée de dette ;
- DSCR cible ;
- cohérence générale de la structure financière.

F. FISCALITÉ
Examiner :
- taux IS ;
- TVA ;
- WHT ;
- durée / politique d'amortissement.

G. RENTABILITÉ
Examiner :
- TRI projet ;
- TRI fonds propres ;
- WACC ;
- taux d'actualisation ;
- relations entre ces indicateurs.

H. TARIF
Examiner :
- niveau du tarif ;
- cohérence avec coûts, dette et rentabilité ;
- inflation éventuelle lorsque disponible.

I. RISQUES ET POINTS D'ATTENTION
Identifier les incohérences, hypothèses agressives,
données manquantes ou éléments nécessitant une revue.

J. RECOMMANDATIONS
Proposer des recommandations d'analyse ou de vérification.
Ne formule pas de conclusion réglementaire définitive.

Retourne UNIQUEMENT un JSON strict de cette forme :

{{
  "synthese_executive": "...",

  "hypotheses_techniques": {{
    "constats": [],
    "points_attention": []
  }},

  "investissement": {{
    "constats": [],
    "points_attention": []
  }},

  "exploitation": {{
    "constats": [],
    "points_attention": []
  }},

  "financement_dette": {{
    "constats": [],
    "points_attention": []
  }},

  "fiscalite": {{
    "constats": [],
    "points_attention": []
  }},

  "rentabilite": {{
    "constats": [],
    "points_attention": []
  }},

  "tarif": {{
    "constats": [],
    "points_attention": []
  }},

  "risques": [],

  "donnees_manquantes_importantes": [],

  "recommandations": []
}}
"""

    return prompt.strip()


# ==========================================================
# 5. Appel du modèle
# ==========================================================

def analyser(registre):

    prompt = construire_prompt(
        registre
    )

    resultat = appeler_json(
        prompt
    )

    if not isinstance(resultat, dict):

        raise RuntimeError(
            "Gemini n'a pas retourné "
            "une analyse JSON valide."
        )

    return resultat


# ==========================================================
# 6. Conversion JSON -> Markdown lisible
# ==========================================================

def _liste_markdown(elements):

    if not elements:
        return "- Aucun élément identifié.\n"

    return "".join(
        f"- {x}\n"
        for x in elements
    )


def generer_markdown(analyse):

    lignes = []

    lignes.append(
        "# Analyse financière ARSEL\n\n"
    )

    lignes.append(
        "## 1. Synthèse exécutive\n\n"
    )

    lignes.append(
        analyse.get(
            "synthese_executive",
            "Non disponible."
        )
        + "\n\n"
    )

    sections = [
        (
            "2. Hypothèses techniques",
            "hypotheses_techniques"
        ),
        (
            "3. Investissement",
            "investissement"
        ),
        (
            "4. Exploitation",
            "exploitation"
        ),
        (
            "5. Financement et dette",
            "financement_dette"
        ),
        (
            "6. Fiscalité",
            "fiscalite"
        ),
        (
            "7. Rentabilité",
            "rentabilite"
        ),
        (
            "8. Tarif",
            "tarif"
        ),
    ]

    for titre, cle in sections:

        contenu = analyse.get(
            cle,
            {}
        ) or {}

        lignes.append(
            f"## {titre}\n\n"
        )

        lignes.append(
            "### Constats\n\n"
        )

        lignes.append(
            _liste_markdown(
                contenu.get(
                    "constats",
                    []
                )
            )
        )

        lignes.append(
            "\n### Points d'attention\n\n"
        )

        lignes.append(
            _liste_markdown(
                contenu.get(
                    "points_attention",
                    []
                )
            )
        )

        lignes.append("\n")


    lignes.append(
        "## 9. Risques et points d'attention\n\n"
    )

    lignes.append(
        _liste_markdown(
            analyse.get(
                "risques",
                []
            )
        )
    )


    lignes.append(
        "\n## 10. Données manquantes importantes\n\n"
    )

    lignes.append(
        _liste_markdown(
            analyse.get(
                "donnees_manquantes_importantes",
                []
            )
        )
    )


    lignes.append(
        "\n## 11. Recommandations\n\n"
    )

    lignes.append(
        _liste_markdown(
            analyse.get(
                "recommandations",
                []
            )
        )
    )

    return "".join(lignes)


# ==========================================================
# 7. Sauvegarde
# ==========================================================

def sauvegarder(
    analyse,
    sortie_json="analyse_financiere.json",
    sortie_md="analyse_financiere.md",
):

    with open(
        sortie_json,
        "w",
        encoding="utf-8"
    ) as f:

        json.dump(
            analyse,
            f,
            ensure_ascii=False,
            indent=2,
            default=str
        )


    markdown = generer_markdown(
        analyse
    )

    with open(
        sortie_md,
        "w",
        encoding="utf-8"
    ) as f:

        f.write(
            markdown
        )

    return sortie_json, sortie_md


# ==========================================================
# MAIN
# ==========================================================

def main():

    chemin = (
        sys.argv[1]
        if len(sys.argv) > 1
        else FICHIER_DEFAUT
    )

    print(
        "\n" + "═"*70
    )

    print(
        "ANALYSE FINANCIÈRE ARSEL"
    )

    print(
        "═"*70
    )

    registre = charger_registre(
        chemin
    )

    disponibles, indisponibles = (
        separer_disponibilite(
            registre
        )
    )

    print(
        f"\nMétriques validées     : "
        f"{len(registre)}"
    )

    print(
        f"Métriques disponibles  : "
        f"{len(disponibles)}"
    )

    print(
        f"Métriques indisponibles: "
        f"{len(indisponibles)}"
    )

    print(
        "\nAnalyse Gemini en cours..."
    )

    analyse = analyser(
        registre
    )

    sortie_json, sortie_md = (
        sauvegarder(
            analyse
        )
    )

    print(
        "\nAnalyse terminée."
    )

    print(
        f"  JSON     → {sortie_json}"
    )

    print(
        f"  Markdown → {sortie_md}"
    )


if __name__ == "__main__":
    main()
