# -*- coding: utf-8 -*-
"""Instrumentation locale des appels LLM, ventilée par métrique ARSEL."""
import time


class InstrumentationLLM:
    def __init__(self, max_appels_par_metrique=1):
        self.max_appels_par_metrique = max_appels_par_metrique
        self._stats = {}

    def _stat(self, metrique):
        return self._stats.setdefault(metrique, {
            "llm_calls": 0, "llm_successes": 0, "llm_failures": 0,
            "latency_ms": 0.0, "last_failure_type": None})

    def instrumenter(self, metrique, fonction):
        def appel(prompt):
            stat = self._stat(metrique)
            if stat["llm_calls"] >= self.max_appels_par_metrique:
                raise RuntimeError(f"Limite LLM dépassée pour {metrique}")
            stat["llm_calls"] += 1
            debut = time.perf_counter()
            try:
                resultat = fonction(prompt)
            except Exception as ex:
                stat["llm_failures"] += 1
                stat["last_failure_type"] = type(ex).__name__
                raise
            else:
                stat["llm_successes"] += 1
                return resultat
            finally:
                stat["latency_ms"] += (time.perf_counter() - debut) * 1000
        return appel

    def pour_metrique(self, metrique):
        stat = dict(self._stat(metrique))
        stat["latency_ms"] = round(stat["latency_ms"], 3)
        return stat

    def resume(self):
        stats = [self.pour_metrique(cle) for cle in self._stats]
        return {"metrics_tracked": len(stats),
                "total_calls": sum(s["llm_calls"] for s in stats),
                "total_successes": sum(s["llm_successes"] for s in stats),
                "total_failures": sum(s["llm_failures"] for s in stats),
                "latency_ms": round(sum(s["latency_ms"] for s in stats), 3)}
