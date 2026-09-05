import unittest
from unittest.mock import patch

from arsel_core.workflow import etape2


def resultat(cle, valeur=1, unite="MW"):
    return {
        "cle": cle,
        "categorie": "factuel",
        "description": cle,
        "adresse": None,
        "resume": str(valeur),
        "unite": unite,
        "detail": {"valeur": valeur},
        "nature": "montant",
        "resolver": "scalar_value",
        "statut": "proposé",
    }


class TestValidationNavigation(unittest.TestCase):
    @patch("builtins.print")
    def test_choix_invalide_reste_sur_la_meme_metrique(self, _print):
        with patch("builtins.input", side_effect=["invalide", "v"]):
            valides = etape2(None, [resultat("puissance")], [])
        self.assertEqual(len(valides), 1)
        self.assertEqual(valides[0]["cle"], "puissance")

    @patch("builtins.print")
    def test_retour_remplace_la_validation_precedente(self, _print):
        resultats = [resultat("premiere"), resultat("seconde")]
        with patch("builtins.input", side_effect=["v", "p", "a", "2", "v"]):
            valides = etape2(None, resultats, [])
        self.assertEqual([x["cle"] for x in valides], ["premiere", "seconde"])
        self.assertEqual(valides[0]["detail"]["valeur"], 2.0)

    @patch("builtins.print")
    def test_lettre_de_commande_ne_devient_pas_une_unite(self, _print):
        metrique = resultat("puissance", unite="MW")
        with patch("builtins.input", side_effect=["u", "u", "v"]):
            valides = etape2(None, [metrique], [])
        self.assertEqual(valides[0]["unite"], "MW")


if __name__ == "__main__":
    unittest.main()
