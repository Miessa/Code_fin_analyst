import unittest

import numpy as np

from arsel_core.embedding_search import IndexEmbeddings, construire_document
from arsel_core.rank_fusion import reciprocal_rank_fusion


def candidat(adresse, libelle, **extras):
    return {
        "cellule_libelle": adresse,
        "adresse_valeur": adresse.replace("A", "B"),
        "libelle": libelle,
        **extras,
    }


class FauxModele:
    """Tiny deterministic encoder used without downloading an external model."""

    def encode(self, textes, **_kwargs):
        vecteurs = []
        for texte in textes:
            normalise = texte.lower()
            if "construction" in normalise or "epc" in normalise:
                vecteurs.append([1.0, 0.0])
            elif "debt" in normalise or "dette" in normalise:
                vecteurs.append([0.0, 1.0])
            else:
                vecteurs.append([0.5, 0.5])
        return np.asarray(vecteurs)


class TestEmbeddingSearch(unittest.TestCase):
    def test_retrouve_epc_par_requete_metier(self):
        catalogue = [
            candidat("Summary!A1", "EPC"),
            candidat("Debt!A2", "Debt maturity"),
        ]
        index = IndexEmbeddings(catalogue, model=FauxModele())
        resultats = index.rechercher({
            "cle": "cout_construction",
            "description": "coût de construction",
        })
        self.assertEqual(resultats[0]["cellule_libelle"], "Summary!A1")
        self.assertIn("score_embedding", resultats[0])

    def test_document_ne_contient_pas_la_valeur(self):
        document = construire_document(candidat(
            "Summary!A1", "EPC", feuille="Summary", valeur=123456
        ))
        self.assertIn("EPC", document)
        self.assertNotIn("123456", document)


class TestRankFusion(unittest.TestCase):
    def test_fusionne_provenance_rangs_et_scores(self):
        epc = candidat("Summary!A1", "EPC")
        dette = candidat("Debt!A2", "Debt maturity")
        fusion = reciprocal_rank_fusion({
            "lexical": [dette, epc],
            "tfidf": [epc],
            "embeddings": [epc],
        })
        self.assertEqual(fusion[0]["cellule_libelle"], "Summary!A1")
        self.assertEqual(
            fusion[0]["sources_retrieval"],
            ["lexical", "tfidf", "embeddings"],
        )
        self.assertEqual(fusion[0]["retrieval_ranks"]["embeddings"], 1)
        self.assertEqual(fusion[0]["score_rrf_normalise"], 1.0)

    def test_refuse_un_parametre_rrf_negatif(self):
        with self.assertRaises(ValueError):
            reciprocal_rank_fusion({}, rrf_k=-1)


if __name__ == "__main__":
    unittest.main()
