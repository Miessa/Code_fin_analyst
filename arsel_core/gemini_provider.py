# -*- coding: utf-8 -*-
"""
gemini_provider.py — APPARIEMENT CONCEPT→LIBELLÉ par recherche sémantique.

Le code fournit le CATALOGUE COMPLET des libellés (adresse + valeur). Le LLM
cherche lui-même le bon libellé et répond par un NUMÉRO (0 = aucun).

Deux modes :
  • chercher()        : un concept -> un numéro (1 appel par concept)
  • chercher_lot()    : TOUS les concepts en UN SEUL appel (catalogue envoyé une
                        seule fois). Réduit d'un facteur ~N le nombre d'appels et
                        la consommation de tokens -> évite le quota 429.

Le LLM ne renvoie que des numéros ; le code traduit en adresses. Aucune adresse
hallucinée possible.
"""
import os
import re
import json

from typing import Literal
from pydantic import BaseModel, Field

from .excel_tools import (
    lire_cellule,
    lire_formule,
    inspecter_voisinage,
)

MODELE_DEFAUT = "gemini-flash-latest"
TEMPERATURE = 0.0

class RerankDecision(BaseModel):
    decision: Literal[
        "selected",
        "need_more_evidence",
        "no_match"
    ]

    selected_candidate: int | None = None

    confidence: float = Field(
        ge=0.0,
        le=1.0
    )

    reason: str


class GeminiIndisponible(Exception):
    pass

class GeminiErreur(Exception):
    pass


class GeminiQuota(GeminiErreur):
    pass


class GeminiTemporaire(GeminiErreur):
    pass


class GeminiReponseInvalide(GeminiErreur):
    pass


class GeminiConfiguration(GeminiErreur):
    pass

def _client(cle=None):
    try:
        from google import genai
    except ImportError:
        raise GeminiIndisponible("paquet 'google-genai' absent")
    cle = cle or os.environ.get("GEMINI_API_KEY")
    if not cle:
        raise GeminiIndisponible("clé absente — définir GEMINI_API_KEY")
    return genai.Client(api_key=cle)

def classifier_erreur_gemini(ex):
    """
    Transforme une exception brute du SDK Gemini
    en catégorie métier stable pour ARSEL.
    """

    message = str(ex).lower()

    # Quota / rate limit
    if (
        "429" in message
        or "resource_exhausted" in message
        or "rate limit" in message
        or "quota" in message
    ):
        return GeminiQuota(str(ex))

    # Erreurs temporaires / serveur / réseau
    if (
        "408" in message
        or "500" in message
        or "502" in message
        or "503" in message
        or "504" in message
        or "unavailable" in message
        or "timeout" in message
        or "timed out" in message
        or "connection" in message
    ):
        return GeminiTemporaire(str(ex))

    # Mauvaise clé / mauvais appel / configuration
    if (
        "400" in message
        or "401" in message
        or "403" in message
        or "api key" in message
        or "permission" in message
    ):
        return GeminiConfiguration(str(ex))

    return GeminiErreur(str(ex))

def _catalogue_texte(catalogue):
    lignes = []
    for i, e in enumerate(catalogue, 1):
        lignes.append(f'{i}. {e["cellule_libelle"]} «{e["libelle"][:60]}» = {e["valeur"]:g}')
    return "\n".join(lignes)


def executer_appel_gemini(
    fonction,
    fallback=None,
    contexte=None
):
    """
    Point unique de gestion des erreurs Gemini.

    fonction :
        fonction sans argument qui effectue
        réellement l'appel API.

    fallback :
        fonction sans argument utilisée
        si Gemini échoue.

    contexte :
        texte utile pour les logs.
    """

    try:
        return fonction()

    except GeminiIndisponible as ex:

        print(
            f"    Gemini indisponible"
            f"{f' [{contexte}]' if contexte else ''} : "
            f"{ex}"
        )

    except Exception as ex:

        erreur = classifier_erreur_gemini(ex)

        if isinstance(erreur, GeminiQuota):

            print(
                f"    Gemini quota/rate limit"
                f"{f' [{contexte}]' if contexte else ''}"
            )

        elif isinstance(
            erreur,
            GeminiTemporaire
        ):

            print(
                f"    Gemini erreur temporaire"
                f"{f' [{contexte}]' if contexte else ''} : "
                f"{ex}"
            )

        elif isinstance(
            erreur,
            GeminiConfiguration
        ):

            print(
                f"    Gemini erreur configuration"
                f"{f' [{contexte}]' if contexte else ''} : "
                f"{ex}"
            )

        else:

            print(
                f"    Gemini erreur"
                f"{f' [{contexte}]' if contexte else ''} : "
                f"{type(ex).__name__}: {ex}"
            )

    # Gemini a échoué
    if fallback is not None:
        return fallback()

    return None

def appeler_structure(
    prompt,
    schema,
    modele=MODELE_DEFAUT,
    cle=None
):
    def _appel():

        client = _client(cle)

        from google.genai import types

        rep = client.models.generate_content(
            model=modele,
            contents=prompt,
            config=types.GenerateContentConfig(
                temperature=TEMPERATURE,
                response_mime_type="application/json",
                response_schema=schema,
            ),
        )

        try:
            return schema.model_validate_json(
                rep.text
            )

        except Exception as ex:
            raise GeminiReponseInvalide(
                f"Structured Output invalide : {ex}"
            )

    return executer_appel_gemini(
        _appel,
        fallback=None,
        contexte="structured_output"
    )

# ---- mode 1 concept -> 1 appel ------------------------------------------
def chercher(concept, description, catalogue, modele=MODELE_DEFAUT, cle=None):
    client = _client(cle)
    if not catalogue:
        return None
    systeme = ("Tu localises une donnée dans un modèle financier. On te donne un "
               "CONCEPT et un CATALOGUE numéroté de libellés. Trouve LE numéro du "
               "libellé correspondant.\n" + REGLES +
               "\nRéponds UNIQUEMENT par le nombre.")
    requete = (f"CONCEPT : {concept} — {description}\n\n"
               f"CATALOGUE ({len(catalogue)} libellés) :\n{_catalogue_texte(catalogue)}\n\n"
               f"Numéro (ou 0) :")
    from google.genai import types
    rep = client.models.generate_content(
        model=modele, contents=requete,
        config=types.GenerateContentConfig(system_instruction=systeme, temperature=TEMPERATURE))
    m = re.search(r"-?\d+", rep.text or "")
    if not m:
        return None
    k = int(m.group(0))
    return catalogue[k - 1] if 1 <= k <= len(catalogue) else None


# ---- mode LOT : tous les concepts en UN SEUL appel ----------------------
def chercher_lot(concepts, catalogue, modele=MODELE_DEFAUT, cle=None):
    """concepts = [{"cle","description"}...]. Retourne {cle: entrée_catalogue|None}.
    Envoie le catalogue UNE fois -> économise appels et tokens (anti-429)."""
    client = _client(cle)
    if not catalogue:
        return {c["cle"]: None for c in concepts}

    liste_concepts = "\n".join(f'- {c["cle"]} : {c["description"]}' for c in concepts)
    systeme = ("Tu localises des données dans un modèle financier. On te donne une "
               "liste de CONCEPTS et un CATALOGUE numéroté de libellés. Pour CHAQUE "
               "concept, trouve le numéro du libellé correspondant.\n" + REGLES +
               "\nRéponds en JSON strict : un objet {\"cle_concept\": numero, ...} ; "
               "numero=0 si aucun. Aucun texte hors du JSON.")
    requete = (f"CONCEPTS :\n{liste_concepts}\n\n"
               f"CATALOGUE ({len(catalogue)} libellés) :\n{_catalogue_texte(catalogue)}\n\n"
               f"JSON {{concept: numéro}} :")
    from google.genai import types
    rep = client.models.generate_content(
        model=modele, contents=requete,
        config=types.GenerateContentConfig(system_instruction=systeme, temperature=TEMPERATURE))
    txt = (rep.text or "").strip()
    # extraire le bloc JSON
    m = re.search(r"\{.*\}", txt, re.DOTALL)
    mapping = {}
    if m:
        try:
            mapping = json.loads(m.group(0))
        except Exception:
            mapping = {}
    resultat = {}
    n = len(catalogue)
    for c in concepts:
        k = mapping.get(c["cle"], 0)
        try:
            k = int(k)
        except Exception:
            k = 0
        resultat[c["cle"]] = catalogue[k - 1] if 1 <= k <= n else None
    return resultat

def appeler_json(
    prompt,
    modele=MODELE_DEFAUT,
    cle=None
):

    def _appel():

        client = _client(cle)

        from google.genai import types

        rep = client.models.generate_content(
            model=modele,
            contents=prompt,
            config=types.GenerateContentConfig(
                temperature=TEMPERATURE
            ),
        )

        txt = (
            rep.text or ""
        ).strip()

        m = re.search(
            r"\{.*\}",
            txt,
            re.DOTALL
        )

        if not m:
            raise GeminiReponseInvalide(
                "aucun JSON détecté"
            )

        try:
            return json.loads(
                m.group(0)
            )

        except Exception as ex:
            raise GeminiReponseInvalide(
                f"JSON invalide : {ex}"
            )

    return executer_appel_gemini(
        _appel,
        fallback=lambda: {},
        contexte="json"
    )

def disponible():
    try:
        _client()
        return True
    except GeminiIndisponible:
        return False


#if __name__ == "__main__":
#    print("Prêt." if disponible() else "Pas prêt : google-genai + GEMINI_API_KEY.")

if __name__ == "__main__":
    print(
        "Prêt."
        if disponible()
        else "Pas prêt : google-genai + GEMINI_API_KEY."
    )


def investiguer_avec_outils(
    concept,
    description,
    candidats,
    wb,
    wb_formules,
    modele=MODELE_DEFAUT,
    cle=None
):
    """
    Permet à Gemini d'inspecter quelques faits Excel
    lorsqu'un rerank classique ne suffit pas.

    Gemini peut :
    - lire une cellule ;
    - lire sa formule ;
    - inspecter son voisinage.

    Le SDK google-genai gère automatiquement
    la boucle de function calling.
    """

   
    # ----------------------------------------------------------
    # Wrappers exposés à Gemini
    # ----------------------------------------------------------

    def lire_cellule_tool(
        adresse: str
    ) -> dict:
        """
        Lit la valeur calculée d'une cellule Excel candidate.

        Args:
            adresse: Adresse au format 'Feuille!Cellule'.

        Returns:
            Adresse et valeur de la cellule.
        """

        return lire_cellule(
            wb,
            adresse
        )


    def lire_formule_tool(
        adresse: str
    ) -> dict:
        """
        Lit la formule Excel originale d'une cellule candidate.

        Args:
            adresse: Adresse au format 'Feuille!Cellule'.

        Returns:
            Adresse et formule éventuelle.
        """

        return lire_formule(
            wb_formules,
            adresse
        )


    def inspecter_voisinage_tool(
        adresse: str,
        rayon: int = 2
    ) -> list:
        """
        Inspecte les cellules non vides autour d'une cellule.

        Args:
            adresse: Adresse au format 'Feuille!Cellule'.
            rayon: Rayon d'inspection, entre 1 et 3.

        Returns:
            Liste des cellules non vides autour de l'adresse.
        """

        rayon = max(
            1,
            min(rayon, 3)
        )

        return inspecter_voisinage(
            wb,
            adresse,
            rayon
        )


    # ----------------------------------------------------------
    # Limiter Gemini aux adresses candidates
    # ----------------------------------------------------------

    adresses_autorisees = []

    for c in candidats:

        if c.get("cellule_libelle"):
            adresses_autorisees.append(
                c["cellule_libelle"]
            )

        if c.get("adresse_valeur"):
            adresses_autorisees.append(
                c["adresse_valeur"]
            )


    lignes = []

    for i, c in enumerate(
        candidats,
        1
    ):

        lignes.append(
            f"{i}. "
            f"label={c.get('cellule_libelle')} "
            f"«{c.get('libelle')}» "
            f"valeur={c.get('adresse_valeur')} "
            f"= {c.get('valeur')} "
            f"score={c.get('score', 0):.3f}"
        )


    prompt = (
        "Tu dois résoudre une ambiguïté entre plusieurs "
        "candidats provenant d'un modèle financier Excel.\n\n"

        f"CONCEPT : {concept}\n"
        f"DESCRIPTION : {description}\n\n"

        "CANDIDATS :\n"
        + "\n".join(lignes)
        + "\n\n"

        "Tu peux utiliser les outils pour inspecter les cellules, "
        "leurs formules et leur voisinage.\n"

        "N'utilise les outils que lorsque cela apporte une preuve "
        "utile au départage.\n"

        "Ne suppose jamais une information absente.\n"

        "À la fin, réponds en JSON avec :\n"
        "{"
        "\"decision\": \"selected|no_match\", "
        "\"selected_candidate\": numéro ou null, "
        "\"confidence\": nombre entre 0 et 1, "
        "\"reason\": \"raison courte\""
        "}"
    )


    from google.genai import types

    def _appel_outils():

        client = _client(cle)

        from google.genai import types

        return client.models.generate_content(
            model=modele,
            contents=prompt,
            config=types.GenerateContentConfig(
                temperature=TEMPERATURE,
                tools=[
                    lire_cellule_tool,
                    lire_formule_tool,
                    inspecter_voisinage_tool,
                ],
            ),
        )


    rep = executer_appel_gemini(
        _appel_outils,
        fallback=None,
        contexte=f"tool_calling:{concept}"
    )


    if rep is None:

        return RerankDecision(
            decision="need_more_evidence",
            selected_candidate=None,
            confidence=0.0,
            reason=(
                "Gemini indisponible pendant "
                "l'inspection Excel"
            )
        )

    preuves = rep.text or ""

    prompt_final = (
        f"CONCEPT : {concept}\n"
        f"DESCRIPTION : {description}\n\n"

        f"CANDIDATS :\n"
        + "\n".join(lignes)
        + "\n\n"

        "INFORMATIONS OBTENUES APRÈS INSPECTION EXCEL :\n"
        f"{preuves}\n\n"

        "À partir uniquement de ces informations, "
        "prends une décision finale."
    )

    return appeler_structure(
        prompt_final,
        RerankDecision,
        modele=modele,
        cle=cle
    )




def departager(concept,description,candidats,wb=None,wb_formules=None,modele=MODELE_DEFAUT,
    cle=None):
    """Départage un PETIT lot de candidats déjà présélectionnés+scorés.
    candidats = [{cellule_libelle, libelle, valeur, score}]. Retourne l'entrée
    choisie (ou la meilleure par score si le LLM échoue). Appel minuscule -> pas de quota."""
    if not candidats:
        return None
    if len(candidats) == 1:
        return candidats[0]
    try:
        client = _client(cle)
    except GeminiIndisponible:
        return max(candidats, key=lambda c: c.get("score", 0))
    lignes = []
    for i, e in enumerate(candidats, 1):
        lignes.append(f'{i}. {e["cellule_libelle"]} «{e["libelle"][:60]}» = {e["valeur"]:g}'
                      f'  [score {e.get("score",0):.2f}]')
    systeme = (
    "Tu départages plusieurs candidats déjà présélectionnés "
    "pour une métrique d'un modèle financier.\n"
    + REGLES
    + "\n"
    "Choisis un candidat uniquement si les informations disponibles "
    "permettent réellement de le départager.\n"
    "Si plusieurs candidats restent plausibles et qu'une inspection "
    "supplémentaire du fichier Excel serait nécessaire, utilise "
    "decision='need_more_evidence'.\n"
    "Si aucun candidat ne correspond au concept, utilise "
    "decision='no_match'.")

    requete = (
        f"{systeme}\n\n"
        f"CONCEPT : {concept}\n"
        f"DESCRIPTION : {description}\n\n"
        f"CANDIDATS :\n"
        + "\n".join(lignes)
    )
    try:
        decision = appeler_structure(
            requete,
            RerankDecision,
            modele=modele,
            cle=cle
        )

        if decision.decision == "selected":

            k = decision.selected_candidate

            if (
                k is not None
                and 1 <= k <= len(candidats)
            ):
                return candidats[k - 1]

            # Gemini dit SELECT mais renvoie
            # un numéro impossible.
            return None

        if decision.decision == "need_more_evidence":

            # Pas de workbook disponible :
            # impossible d'investiguer
            if (
                wb is None
                or wb_formules is None
            ):
                return None

            decision_2 = (
                investiguer_avec_outils(
                    concept=concept,
                    description=description,
                    candidats=candidats,
                    wb=wb,
                    wb_formules=wb_formules,
                    modele=modele,
                    cle=cle
                )
            )

            if (
                decision_2.decision
                == "selected"
            ):

                k = (
                    decision_2
                    .selected_candidate
                )

                if (
                    k is not None
                    and
                    1 <= k <= len(candidats)
                ):
                    return candidats[
                        k - 1
                    ]

            return None

        if decision.decision == "no_match":
            return None

    except Exception:
        pass
    # repli déterministe : meilleur score
    return max(candidats, key=lambda c: c.get("score", 0))
