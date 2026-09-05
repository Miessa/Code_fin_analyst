# -*- coding: utf-8 -*-
"""Local multilingual semantic retrieval for workbook labels.

The sentence-transformers dependency and model are loaded lazily.  Callers can
therefore keep using the deterministic and TF-IDF pipeline when the optional
embedding stack is unavailable.
"""

from __future__ import annotations

import numpy as np

from .tfidf_search import construire_requete


DEFAULT_MODEL = "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"


def construire_document(candidat):
    """Build a concise semantic representation without exposing the value."""
    champs = (
        ("Label", candidat.get("libelle")),
        ("Sheet", candidat.get("feuille")),
        ("Section", candidat.get("section")),
        ("Context", candidat.get("contexte")),
        ("Header", candidat.get("contexte_haut")),
        ("Unit", candidat.get("unite_detectee")),
    )
    return ". ".join(f"{nom}: {valeur}" for nom, valeur in champs if valeur)


class IndexEmbeddings:
    """Encode a workbook catalog once and reuse it for every ARSEL concept."""

    def __init__(self, catalogue, model_name=DEFAULT_MODEL, model=None):
        self.catalogue = list(catalogue or [])
        self.model_name = model_name
        if model is None:
            from sentence_transformers import SentenceTransformer
            model = SentenceTransformer(model_name)
        self.model = model
        self.documents = [construire_document(c) for c in self.catalogue]
        self.matrix = None
        if self.documents:
            self.matrix = np.asarray(
                self.model.encode(
                    self.documents,
                    batch_size=64,
                    normalize_embeddings=True,
                    show_progress_bar=False,
                ),
                dtype=float,
            )

    def rechercher(self, concept, k=20, candidats_deja_vus=None):
        if k <= 0 or self.matrix is None or not len(self.catalogue):
            return []
        requete = construire_requete(concept)
        if not requete.strip():
            return []
        vecteur = np.asarray(
            self.model.encode(
                [requete], normalize_embeddings=True, show_progress_bar=False
            ),
            dtype=float,
        )[0]
        scores = self.matrix @ vecteur
        deja_vus = {
            c.get("cellule_libelle") if isinstance(c, dict) else c
            for c in (candidats_deja_vus or [])
        }
        resultat = []
        for indice in np.argsort(-scores, kind="stable"):
            candidat = self.catalogue[int(indice)]
            if candidat.get("cellule_libelle") in deja_vus:
                continue
            resultat.append({
                **candidat,
                "score_embedding": round(float(scores[indice]), 6),
                "embedding_model": self.model_name,
            })
            if len(resultat) >= k:
                break
        return resultat


def creer_index_embeddings(catalogue, model_name=DEFAULT_MODEL):
    """Return ``(index, error)`` so missing optional dependencies are harmless."""
    try:
        return IndexEmbeddings(catalogue, model_name=model_name), None
    except Exception as exc:
        return None, f"{type(exc).__name__}: {exc}"
