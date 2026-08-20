# -*- coding: utf-8 -*-
import unittest

from arsel_core.collecter_libelles import FEUILLES_DEFAUT, _libelle_admis


class TestCollecterLibelles(unittest.TestCase):
    def test_inclut_fs_ann(self):
        self.assertIn("FS_Ann", FEUILLES_DEFAUT)

    def test_accepte_un_acronyme_de_trois_caracteres(self):
        self.assertTrue(_libelle_admis("EPC"))
        self.assertTrue(_libelle_admis("IRR"))

    def test_rejette_les_textes_trop_courts_ou_trop_longs(self):
        self.assertFalse(_libelle_admis("EP"))
        self.assertFalse(_libelle_admis("X" * 80))


if __name__ == "__main__":
    unittest.main()
