import unittest
from phase2.peer_benchmark import enrich_professional_analysis, position_project


class PeerBenchmarkTests(unittest.TestCase):
    def test_position_and_reliability(self):
        selection = {"selection_status": "analyst_approved", "approved_project_ids": ["a","b","c","d","e"],
            "decisions": [{"project_id":"a","project_name":"A","decision":"approved","score":.9}],
            "benchmark_statistics": [{"metric":"debt_share","unit":"ratio","sample_size":5,
                "minimum":.5,"p25":.6,"median":.65,"mean":.66,"p75":.7,"maximum":.75,
                "project_ids":["a","b","c","d","e"]}]}
        item = position_project(selection, [], [{"cle":"debt_share","valeur":.8}])["comparisons"][0]
        self.assertEqual(item["position"], "ABOVE_MAX")
        self.assertEqual(item["reliability"], "usable")

    def test_peer_deviation_enters_summary_and_risks(self):
        analysis = {"synthese_executive":"Résumé.", "risques":[], "recommandations":[]}
        peer = {"status":"APPLIED", "approved_count":5, "comparisons":[{
            "label":"Part de dette", "position":"ABOVE_MAX", "reliability":"usable",
            "comment":"valeur supérieure au maximum des pairs."}]}
        enriched = enrich_professional_analysis(analysis, peer)
        self.assertIn("5 projet(s)", enriched["synthese_executive"])
        self.assertTrue(enriched["risques"])

    def test_absent_selection_non_blocking(self):
        self.assertEqual(position_project(None, [], [])["status"], "NOT_PERFORMED")

if __name__ == "__main__": unittest.main()
