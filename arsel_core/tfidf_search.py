# -*- coding: utf-8 -*-
"""Recherche locale de candidats Excel par TF-IDF.

Ce module fait uniquement du retrieval : il propose les libellés qui méritent
d'être caractérisés par les couches structurelles. Il ne choisit jamais la
cellule finale et ne lit pas le classeur Excel.

L'index est construit une seule fois à partir du catalogue retourné par
``collecter()`` puis réutilisé pour tous les concepts ARSEL.
"""

import re
import unicodedata

import numpy as np
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity


def _normaliser(texte):
    texte = unicodedata.normalize("NFD", str(texte or "").lower())
    texte = "".join(
        caractere
        for caractere in texte
        if unicodedata.category(caractere) != "Mn"
    )
    return " ".join(re.findall(r"[a-z0-9]+", texte))


def _elements(valeur):
    if valeur is None:
        return []
    if isinstance(valeur, str):
        return [valeur]
    return [str(element) for element in valeur if element]


def construire_requete(concept):
    """Construit une requête pondérée à partir du référentiel ARSEL.

    Répéter les champs importants est une manière simple et explicite de leur
    donner plus de poids dans le vecteur TF-IDF : les synonymes métier dominent
    ainsi la définition, souvent plus longue et moins discriminante.
    """

    prioritaires = (
        _elements(concept.get("mots_cles"))
        + _elements(concept.get("semantique_positive"))
    )
    secondaires = [concept.get("cle"), concept.get("description")]
    definition = [concept.get("definition")]

    morceaux = prioritaires * 3 + secondaires * 2 + definition
    return " ".join(str(x) for x in morceaux if x)


class IndexTfidf:
    """Index hybride mot/caractère, construit une fois par catalogue."""

    def __init__(
        self,
        catalogue,
        poids_mots=0.7,
        poids_caracteres=0.3,
        poids_contexte=0.0,
    ):
        if poids_mots < 0 or poids_caracteres < 0:
            raise ValueError("Les poids TF-IDF doivent être positifs.")
        total = poids_mots + poids_caracteres
        if total <= 0:
            raise ValueError("Au moins un poids TF-IDF doit être non nul.")

        self.catalogue = list(catalogue or [])
        self.poids_mots = poids_mots / total
        self.poids_caracteres = poids_caracteres / total
        self.poids_contexte = max(0.0, float(poids_contexte))
        self._documents = [self._document(c) for c in self.catalogue]
        self._contextes = [self._contexte(c) for c in self.catalogue]

        self.vectoriseur_mots = None
        self.vectoriseur_caracteres = None
        self.matrice_mots = None
        self.matrice_caracteres = None
        self.vectoriseur_contexte = None
        self.matrice_contexte = None

        if self._documents and any(document.strip() for document in self._documents):
            self.vectoriseur_mots = TfidfVectorizer(
                strip_accents="unicode",
                lowercase=True,
                ngram_range=(1, 2),
                token_pattern=r"(?u)\b\w+\b",
                sublinear_tf=True,
            )
            self.vectoriseur_caracteres = TfidfVectorizer(
                strip_accents="unicode",
                lowercase=True,
                analyzer="char_wb",
                ngram_range=(3, 5),
                sublinear_tf=True,
            )
            self.matrice_mots = self.vectoriseur_mots.fit_transform(
                self._documents
            )
            self.matrice_caracteres = (
                self.vectoriseur_caracteres.fit_transform(self._documents)
            )
            if any(contexte.strip() for contexte in self._contextes):
                self.vectoriseur_contexte = TfidfVectorizer(
                    strip_accents="unicode",
                    lowercase=True,
                    ngram_range=(1, 2),
                    token_pattern=r"(?u)\b\w+\b",
                    sublinear_tf=True,
                )
                self.matrice_contexte = self.vectoriseur_contexte.fit_transform(
                    self._contextes
                )

    @staticmethod
    def _document(candidat):
        return str(candidat.get("libelle") or "")

    @staticmethod
    def _contexte(candidat):
        # Le contexte possède son propre espace vectoriel et un faible poids :
        # il peut départager deux libellés sans diluer le signal principal.
        champs = [
            candidat.get("feuille"),
            candidat.get("section"),
            candidat.get("contexte"),
        ]
        return " ".join(str(x) for x in champs if x)

    def rechercher(self, concept, k=20, candidats_deja_vus=None):
        """Retourne au plus ``k`` candidats, triés par similarité décroissante."""

        if (
            k <= 0
            or not self.catalogue
            or self.vectoriseur_mots is None
        ):
            return []

        requete = construire_requete(concept)
        if not requete.strip():
            return []

        q_mots = self.vectoriseur_mots.transform([requete])
        q_caracteres = self.vectoriseur_caracteres.transform([requete])
        scores_mots = cosine_similarity(q_mots, self.matrice_mots)[0]
        scores_caracteres = cosine_similarity(
            q_caracteres, self.matrice_caracteres
        )[0]
        scores = (
            self.poids_mots * scores_mots
            + self.poids_caracteres * scores_caracteres
        )
        scores_contexte = np.zeros(len(self.catalogue))
        if self.vectoriseur_contexte is not None:
            q_contexte = self.vectoriseur_contexte.transform([requete])
            scores_contexte = cosine_similarity(
                q_contexte, self.matrice_contexte
            )[0]
            scores = scores + self.poids_contexte * scores_contexte

        negatifs = list(
            filter(
                None,
                map(
                    _normaliser,
                    _elements(concept.get("semantique_negative")),
                ),
            )
        )
        deja_vus = {
            c.get("cellule_libelle") if isinstance(c, dict) else c
            for c in (candidats_deja_vus or [])
        }

        nombres_penalites = np.array(
            [
                sum(
                    negatif in _normaliser(candidat.get("libelle"))
                    for negatif in negatifs
                )
                for candidat in self.catalogue
            ]
        )
        scores_finaux = np.maximum(0.0, scores - 0.08 * nombres_penalites)

        resultat = []
        # Trier après les pénalités ; en cas d'égalité, conserver l'ordre du
        # catalogue afin que les résultats restent parfaitement déterministes.
        for indice in np.argsort(-scores_finaux, kind="stable"):
            candidat = self.catalogue[int(indice)]
            adresse = candidat.get("cellule_libelle")
            if adresse in deja_vus:
                continue

            nb_negatifs = int(nombres_penalites[indice])
            score_brut = float(scores[indice])
            score_final = float(scores_finaux[indice])

            # Un résultat sans aucun signal lexical ne constitue pas un
            # candidat utile, même lorsqu'il reste de la place dans le Top K.
            if score_brut <= 0:
                continue

            resultat.append(
                {
                    **candidat,
                    "score_tfidf": round(score_final, 6),
                    "score_tfidf_brut": round(score_brut, 6),
                    "score_tfidf_mots": round(float(scores_mots[indice]), 6),
                    "score_tfidf_caracteres": round(
                        float(scores_caracteres[indice]), 6
                    ),
                    "score_tfidf_contexte": round(
                        float(scores_contexte[indice]), 6
                    ),
                    "penalites_semantiques": nb_negatifs,
                }
            )
            if len(resultat) >= k:
                break

        # La pénalité sémantique peut modifier l'ordre du score hybride brut.
        resultat.sort(key=lambda c: c["score_tfidf"], reverse=True)
        return resultat


def rechercher_tfidf(
    concept,
    catalogue,
    k=20,
    candidats_deja_vus=None,
):
    """Raccourci pratique ; préférer ``IndexTfidf`` pour plusieurs concepts."""

    return IndexTfidf(catalogue).rechercher(
        concept,
        k=k,
        candidats_deja_vus=candidats_deja_vus,
    )


def fusionner_candidats(candidats_lexicaux, candidats_tfidf):
    """Fusionne deux retrievals sans perdre leur provenance ni leurs scores."""

    resultat = []
    par_adresse = {}
    for source, candidats in (
        ("lexical", candidats_lexicaux or []),
        ("tfidf", candidats_tfidf or []),
    ):
        for candidat in candidats:
            adresse = candidat.get("cellule_libelle")
            if not adresse:
                continue
            if adresse not in par_adresse:
                fusionne = {**candidat, "sources_retrieval": [source]}
                par_adresse[adresse] = fusionne
                resultat.append(fusionne)
            else:
                fusionne = par_adresse[adresse]
                if source not in fusionne["sources_retrieval"]:
                    fusionne["sources_retrieval"].append(source)
                # Les résultats TF-IDF portent les scores diagnostiques que la
                # présélection lexicale historique ne calcule pas.
                champs_retrieval = {
                    "penalites_semantiques", "dependency_count", "leaf_count",
                    "has_aggregate_formula", "max_depth_reached",
                    "dependency_boost", "score_retrieval_final",
                }
                for cle, valeur in candidat.items():
                    if cle.startswith("score_tfidf") or cle in champs_retrieval:
                        fusionne[cle] = valeur
    return resultat
