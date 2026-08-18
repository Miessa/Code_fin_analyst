# -*- coding: utf-8 -*-
"""
preselection.py — PRÉSÉLECTION déterministe des candidats d'un concept.

Avant le LLM : réduire le catalogue complet (~2800 libellés) à quelques candidats
plausibles par concept, en s'appuyant sur la SÉMANTIQUE de l'ontologie
(semantique_positive / semantique_negative / description). Purement lexical et
déterministe. Objectif : n'envoyer au LLM qu'une poignée de candidats -> pas de
quota 429, et un rerank ciblé.
"""
import re
import unicodedata


def _norm(s):
    s = unicodedata.normalize("NFD", (s or "").lower())
    s = "".join(c for c in s if unicodedata.category(c) != "Mn")
    return s


def _tokens(s):
    return set(re.findall(r"[a-z0-9&]+", _norm(s)))


def preselectionner(concept, catalogue, k=8):
    """Retourne les k meilleurs candidats du catalogue pour ce concept.
    Score lexical = recouvrement avec semantique_positive (+) et description,
    moins la présence de termes semantique_negative (-)."""
    pos = concept.get("semantique_positive", []) + concept.get("mots_cles", [])
    neg = concept.get("semantique_negative", [])
    desc_tokens = _tokens(concept.get("description", "")) | _tokens(concept.get("cle", ""))
    pos_tokens = set()
    for p in pos:
        pos_tokens |= _tokens(p)
    neg_phrases = [_norm(n) for n in neg]

    notes = []
    for e in catalogue:
        lib_norm = _norm(e["libelle"])
        lib_tokens = _tokens(e["libelle"])
        # score positif : recouvrement de tokens
        s_pos = len(lib_tokens & pos_tokens) * 2 + len(lib_tokens & desc_tokens)
        # bonus si une phrase positive entière est présente
        for p in pos:
            if _norm(p) in lib_norm and len(p) > 4:
                s_pos += 3
        # malus si une phrase négative est présente
        s_neg = sum(2 for n in neg_phrases if n and n in lib_norm)
        score = s_pos - s_neg
        if score > 0:
            notes.append((score, e))

    notes.sort(key=lambda x: x[0], reverse=True)
    return [e for _, e in notes[:k]]
