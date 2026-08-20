# -*- coding: utf-8 -*-
import unittest

from evaluation.evaluer_tfidf import evaluer, normaliser_registre
from arsel_core.tfidf_search import IndexTfidf


class TestEvaluationTfidf(unittest.TestCase):
    def setUp(self):
        self.catalogue = [
            {"cellule_libelle": "InpC!A1", "libelle": "Target leverage"},
            {"cellule_libelle": "InpC!A2", "libelle": "Debt maturity"},
            {"cellule_libelle": "InpC!A3", "libelle": "Total EPC costs"},
        ]
        self.concepts = {
            "gearing": {"cle": "gearing", "mots_cles": ["leverage"]},
            "capex": {"cle": "capex", "mots_cles": ["EPC costs"]},
        }

    def test_calcule_rappel_et_mrr(self):
        rapport = evaluer(
            IndexTfidf(self.catalogue),
            self.concepts,
            [
                {"cle": "gearing", "adresse": "InpC!A1"},
                {"cle": "capex", "adresse": "InpC!A3"},
            ],
        )
        self.assertEqual(rapport["nombre_evalue"], 2)
        self.assertEqual(rapport["recall@5"], 1.0)
        self.assertEqual(rapport["mrr"], 1.0)

    def test_accepte_plusieurs_adresses_valides(self):
        rapport = evaluer(
            IndexTfidf(self.catalogue),
            self.concepts,
            [{"cle": "gearing", "adresses": ["X!A1", "InpC!A1"]}],
        )
        self.assertEqual(rapport["details"][0]["rang"], 1)

    def test_ignore_les_entrees_non_evaluables(self):
        rapport = evaluer(
            IndexTfidf(self.catalogue),
            self.concepts,
            [
                {"cle": "gearing", "adresse": None},
                {"cle": "inconnu", "adresse": "InpC!A1"},
            ],
        )
        self.assertEqual(rapport["nombre_evalue"], 0)
        self.assertEqual(rapport["nombre_ignore"], 2)
        self.assertIsNone(rapport["recall@20"])

    def test_rejette_un_registre_invalide(self):
        with self.assertRaises(ValueError):
            evaluer(IndexTfidf(self.catalogue), self.concepts, {})

    def test_accepte_le_format_ground_truth_enrichi(self):
        document = {
            "metadata": {"workbook": "modele.xlsm"},
            "metrics": {
                "gearing": {
                    "label_addresses": ["InpC!A1"],
                    "evaluation_enabled": True,
                },
                "wacc": {
                    "label_addresses": [],
                    "evaluation_enabled": False,
                },
            },
        }
        rapport = evaluer(
            IndexTfidf(self.catalogue), self.concepts, document
        )
        self.assertEqual(rapport["nombre_evalue"], 1)
        self.assertEqual(rapport["nombre_ignore"], 1)
        self.assertEqual(rapport["details"][0]["rang"], 1)

    def test_extrait_les_adresses_de_series(self):
        document = {
            "metrics": {
                "gearing": {
                    "series": [{"label_address": "InpC!A1"}],
                    "evaluation_enabled": True,
                }
            }
        }
        normalise = normaliser_registre(document)
        rapport = evaluer(
            IndexTfidf(self.catalogue), self.concepts, normalise
        )
        self.assertEqual(rapport["details"][0]["rang"], 1)


if __name__ == "__main__":
    unittest.main()
