import unittest
from arsel_core.semantic_selector import *


class TestSemanticSelector(unittest.TestCase):
    def setUp(self):
        self.candidats = [{"cellule_libelle": "InpC!E17", "libelle": "Leverage"}]

    def test_selected(self):
        r = choisir_semantiquement({}, self.candidats, lambda _: {
            "selection_outcome": "SELECTED", "cellule_libelle": "InpC!E17",
            "confiance_semantique": .9})
        self.assertEqual((r["selection_outcome"], r["execution_status"]),
                         (OUTCOME_SELECTED, STATUS_SUCCESS))

    def test_aucun_candidat(self):
        r = choisir_semantiquement({}, [], lambda _: self.fail())
        self.assertEqual((r["selection_outcome"], r["execution_status"]),
                         (OUTCOME_NO_MATCH, STATUS_NOT_REQUIRED))

    def test_indisponibilite(self):
        def echouer(_): raise TimeoutError("quota")
        r = choisir_semantiquement({}, self.candidats, echouer)
        self.assertEqual((r["selection_outcome"], r["execution_status"]),
                         (OUTCOME_AMBIGUOUS, STATUS_LLM_UNAVAILABLE))

    def test_reponse_invalide_ou_cellule_inventee(self):
        for rep in ({"decision": "select"},
                    {"selection_outcome": "SELECTED", "cellule_libelle": "Fake!A1"}):
            r = choisir_semantiquement({}, self.candidats, lambda _, rep=rep: rep)
            self.assertEqual(r["execution_status"], STATUS_INVALID_RESPONSE)


if __name__ == "__main__": unittest.main()
