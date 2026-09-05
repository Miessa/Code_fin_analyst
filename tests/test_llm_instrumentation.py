import unittest
from arsel_core.llm_instrumentation import InstrumentationLLM


class TestInstrumentationLLM(unittest.TestCase):
    def test_compte_et_limite(self):
        i = InstrumentationLLM(); appel = i.instrumenter("gearing", lambda _: {"ok": True})
        self.assertEqual(appel("p"), {"ok": True})
        with self.assertRaises(RuntimeError): appel("p2")
        self.assertEqual(i.pour_metrique("gearing")["llm_calls"], 1)

    def test_compte_echec(self):
        def echouer(_): raise TimeoutError()
        i = InstrumentationLLM(); appel = i.instrumenter("tarif", echouer)
        with self.assertRaises(TimeoutError): appel("p")
        self.assertEqual(i.pour_metrique("tarif")["llm_failures"], 1)

    def test_reponse_fallback_vide_comptee_comme_echec(self):
        i = InstrumentationLLM()
        appel = i.instrumenter("wacc", lambda _: {})
        self.assertEqual(appel("p"), {})
        stats = i.pour_metrique("wacc")
        self.assertEqual(stats["llm_successes"], 0)
        self.assertEqual(stats["llm_failures"], 1)


if __name__ == "__main__": unittest.main()
