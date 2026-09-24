# -*- coding: utf-8 -*-
import unittest

from arsel_core.business_rules import evaluer_compatibilite


class TestBusinessRulesRegressions(unittest.TestCase):
    def test_project_cost_est_prefere_aux_seuls_couts_financiers(self):
        concept = {"cle": "investissement_total"}
        project = {
            "libelle": "Project Cost",
            "contexte": "Financing assumptions",
            "valeur": 2_472_419,
        }
        financing = {"libelle": "Total financing cost", "valeur": 530_709}
        self.assertEqual(evaluer_compatibilite(concept, project)[0], 1.0)
        self.assertLess(evaluer_compatibilite(concept, financing)[0], 0.5)

    def test_tranche_de_dette_peut_avoir_une_duree_valide(self):
        concept = {"cle": "duree_dette"}
        candidate = {
            "libelle": "Senior debt tenor door to door maturity - Tranche 1",
            "valeur": 18,
        }
        self.assertEqual(evaluer_compatibilite(concept, candidate)[0], 1.0)

    def test_length_of_operations_est_une_duree_de_concession(self):
        concept = {"cle": "duree_concession"}
        candidate = {"libelle": "Length of operations", "valeur": 35}
        self.assertEqual(evaluer_compatibilite(concept, candidate)[0], 1.0)

    def test_zero_reste_aberrant(self):
        factor, _, negatives = evaluer_compatibilite(
            {"cle": "wacc"}, {"libelle": "WACC", "valeur": 0}
        )
        self.assertEqual(factor, 0.0)
        self.assertTrue(any("nulle" in item for item in negatives))


if __name__ == "__main__":
    unittest.main()
