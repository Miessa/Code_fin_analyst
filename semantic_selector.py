# -*- coding: utf-8 -*-

"""
semantic_selector.py

Rôle :
    départager SÉMANTIQUEMENT des candidats déjà compatibles
    structurellement.

Ce module ne lit PAS Excel.
Il ne détecte PAS les structures.
Il ne résout PAS les valeurs.

Il répond uniquement :

    SELECT  -> un candidat correspond réellement au concept
    EXPLORE -> aucun candidat n'est suffisamment convaincant

La partie appel LLM est injectée sous forme de fonction afin de
ne pas coupler cette couche directement à Gemini/OpenAI.
"""

import json


DECISION_SELECT = "select"
DECISION_EXPLORE = "explore"


def _simplifier_candidat(candidat):
    """
    Ne transmet au LLM que les informations utiles à la décision
    sémantique.
    """

    diag = candidat.get("diag") or {}

    return {
        "cellule_libelle": candidat.get("cellule_libelle"),
        "adresse_valeur": candidat.get("adresse_valeur"),
        "libelle": candidat.get("libelle"),
        "valeur": candidat.get("valeur"),

        "score_structurel": candidat.get("score"),

        "structure": diag.get("structure"),
        "value_type": diag.get("value_type"),
        "unit_family": diag.get("unit_family"),
        "temporal_scope": diag.get("temporal_scope"),

        "signaux_positifs": candidat.get(
            "signaux_pos",
            []
        ),

        "signaux_negatifs": candidat.get(
            "signaux_neg",
            []
        ),
    }


def construire_prompt(concept, candidats):
    """
    Construit la demande de décision sémantique envoyée au LLM.
    """

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

    candidats_llm = [
        _simplifier_candidat(c)
        for c in candidats
    ]

    prompt = f"""
Tu es un analyste expert des modèles financiers de projets
d'infrastructure et d'énergie.

Tu dois identifier quel candidat correspond réellement au
CONCEPT MÉTIER demandé.

IMPORTANT :

- Le score_structurel ne mesure PAS la pertinence sémantique.
- Un candidat peut avoir un score structurel de 1.0 tout en
  représentant une mauvaise métrique.
- Ne sélectionne pas un candidat uniquement parce qu'il contient
  un mot proche.
- Distingue le concept économique recherché des métriques voisines.
- Si aucun candidat ne correspond suffisamment au concept,
  réponds EXPLORE.
- N'invente jamais une cellule qui n'est pas dans la liste.
- Pour SELECT, cellule_libelle doit être exactement l'une des
  cellules fournies.

CONCEPT ARSEL :

{json.dumps(
    concept_llm,
    ensure_ascii=False,
    indent=2
)}

CANDIDATS :

{json.dumps(
    candidats_llm,
    ensure_ascii=False,
    indent=2,
    default=str
)}

Tu dois retourner UNIQUEMENT un JSON valide de cette forme :

{{
  "decision": "select" ou "explore",
  "cellule_libelle": "Feuille!Cellule" ou null,
  "confiance_semantique": nombre entre 0 et 1,
  "raison": "explication courte et précise"
}}

Règles :

1. SELECT seulement si un candidat correspond réellement
   au concept métier.

2. EXPLORE si :
   - les candidats correspondent à des concepts voisins ;
   - ils sont trop ambigus ;
   - ou le vrai concept semble absent de la liste.

3. La confiance porte sur la correspondance SÉMANTIQUE,
   pas sur la structure Excel.
"""

    return prompt.strip()


def valider_decision(decision, candidats):
    """
    Vérifie qu'une décision du LLM respecte le contrat.
    """

    if not isinstance(decision, dict):
        return None

    type_decision = decision.get("decision")

    if type_decision not in (
        DECISION_SELECT,
        DECISION_EXPLORE,
    ):
        return None

    # ----------------------------------------------------------
    # EXPLORE
    # ----------------------------------------------------------

    if type_decision == DECISION_EXPLORE:

        return {
            "decision": DECISION_EXPLORE,
            "cellule_libelle": None,
            "confiance_semantique": float(
                decision.get(
                    "confiance_semantique",
                    0.0
                )
            ),
            "raison": decision.get(
                "raison",
                ""
            ),
        }

    # ----------------------------------------------------------
    # SELECT
    # ----------------------------------------------------------

    adresse = decision.get("cellule_libelle")

    adresses_autorisees = {
        c.get("cellule_libelle")
        for c in candidats
    }

    # Le LLM n'a PAS le droit d'inventer une cellule.
    if adresse not in adresses_autorisees:
        return None

    try:
        confiance = float(
            decision.get(
                "confiance_semantique",
                0.0
            )
        )
    except Exception:
        confiance = 0.0

    confiance = max(
        0.0,
        min(1.0, confiance)
    )

    return {
        "decision": DECISION_SELECT,
        "cellule_libelle": adresse,
        "confiance_semantique": confiance,
        "raison": decision.get(
            "raison",
            ""
        ),
    }


def choisir_semantiquement(
    concept,
    candidats,
    appeler_llm_json,
):
    """
    Point d'entrée du semantic selector.

    appeler_llm_json :
        fonction prenant un prompt et retournant un dict JSON.

    Exemple :
        decision = choisir_semantiquement(
            concept,
            candidats,
            appeler_llm_json
        )
    """

    if not candidats:
        return {
            "decision": DECISION_EXPLORE,
            "cellule_libelle": None,
            "confiance_semantique": 0.0,
            "raison": "Aucun candidat disponible.",
        }

    prompt = construire_prompt(
        concept,
        candidats
    )

    try:
        brut = appeler_llm_json(prompt)

    except Exception as ex:

        return {
            "decision": DECISION_EXPLORE,
            "cellule_libelle": None,
            "confiance_semantique": 0.0,
            "raison": (
                f"Échec du semantic selector : "
                f"{type(ex).__name__}: {ex}"
            ),
        }

    decision = valider_decision(
        brut,
        candidats
    )

    if decision is None:

        return {
            "decision": DECISION_EXPLORE,
            "cellule_libelle": None,
            "confiance_semantique": 0.0,
            "raison": (
                "Réponse LLM invalide ou cellule "
                "non autorisée."
            ),
        }

    return decision