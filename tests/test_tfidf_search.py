# -*- coding: utf-8 -*-
import unittest

from arsel_core.tfidf_search import IndexTfidf, construire_requete, fusionner_candidats


def candidat(adresse, libelle):
    return {
        "cellule_libelle": adresse,
        "libelle": libelle,
        "adresse_valeur": adresse.replace("A", "B"),
        "valeur": 0.0,
    }


class TestIndexTfidf(unittest.TestCase):
    def setUp(self):
        self.catalogue = [
            candidat("InpC!A1", "Target leverage (Max allowed)"),
            candidat("InpC!A2", "Total EPC costs"),
            candidat("InpC!A3", "Debt maturity period"),
            candidat("InpC!A4", "Equity internal rate of return"),
            candidat("InpC!A5", "Corporate income tax rate"),
        ]
        self.index = IndexTfidf(self.catalogue)

    def test_retrouve_un_synonyme_fourni_par_le_referentiel(self):
        concept = {
            "cle": "gearing",
            "description": "part de la dette dans le financement",
            "mots_cles": ["gearing", "leverage", "debt ratio"],
            "semantique_positive": ["target leverage"],
        }
        resultats = self.index.rechercher(concept, k=3)
        self.assertEqual(resultats[0]["cellule_libelle"], "InpC!A1")
        self.assertGreater(resultats[0]["score_tfidf"], 0)

    def test_ngrammes_caracteres_tolerent_une_variante(self):
        concept = {
            "cle": "cout_construction",
            "mots_cles": ["EPC cost"],
        }
        resultats = self.index.rechercher(concept, k=1)
        self.assertEqual(resultats[0]["cellule_libelle"], "InpC!A2")
        self.assertGreater(resultats[0]["score_tfidf_caracteres"], 0)

    def test_exclut_les_candidats_deja_vus(self):
        concept = {"mots_cles": ["debt maturity"]}
        resultats = self.index.rechercher(
            concept,
            candidats_deja_vus=[self.catalogue[2]],
        )
        self.assertNotIn(
            "InpC!A3",
            [r["cellule_libelle"] for r in resultats],
        )

    def test_penalise_la_semantique_negative(self):
        catalogue = [
            candidat("InpC!A1", "Total EPC cost including WHT"),
            candidat("InpC!A2", "Total EPC cost"),
        ]
        index = IndexTfidf(catalogue)
        resultats = index.rechercher(
            {
                "mots_cles": ["total EPC cost"],
                "semantique_negative": ["including WHT"],
            },
            k=2,
        )
        self.assertEqual(resultats[0]["cellule_libelle"], "InpC!A2")
        self.assertEqual(resultats[1]["penalites_semantiques"], 1)

    def test_catalogue_ou_requete_vide(self):
        self.assertEqual(IndexTfidf([]).rechercher({"cle": "gearing"}), [])
        self.assertEqual(
            IndexTfidf([candidat("InpC!A1", "")]).rechercher(
                {"cle": "gearing"}
            ),
            [],
        )
        self.assertEqual(self.index.rechercher({}, k=20), [])
        self.assertEqual(self.index.rechercher({"cle": "gearing"}, k=0), [])

    def test_requete_pondere_les_synonymes(self):
        requete = construire_requete(
            {
                "cle": "gearing",
                "mots_cles": ["leverage"],
                "definition": "Capital structure ratio",
            }
        )
        self.assertEqual(requete.split().count("leverage"), 3)
        self.assertEqual(requete.split().count("gearing"), 2)

    def test_fusionne_les_retrievals_et_conserve_les_scores(self):
        lexical = [candidat("InpC!A1", "Target leverage")]
        tfidf = [
            {**lexical[0], "score_tfidf": 0.8, "dependency_boost": 0.1},
            candidat("InpC!A2", "Debt ratio"),
        ]
        fusion = fusionner_candidats(lexical, tfidf)
        self.assertEqual(len(fusion), 2)
        self.assertEqual(fusion[0]["sources_retrieval"], ["lexical", "tfidf"])
        self.assertEqual(fusion[0]["score_tfidf"], 0.8)
        self.assertEqual(fusion[0]["dependency_boost"], 0.1)


if __name__ == "__main__":
    unittest.main()
