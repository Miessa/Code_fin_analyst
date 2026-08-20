"""Bounded LLM assistance with 503 backoff, checkpointing and circuit breaker."""

import json
import random
import time
from pathlib import Path

from arsel_core.gemini_provider import _client, classifier_erreur_gemini, GeminiTemporaire, GeminiQuota


class ResilientLLMExtractor:
    def __init__(self, checkpoint, max_calls=3, attempts=3, circuit_threshold=2, call=None):
        self.checkpoint = Path(checkpoint)
        self.max_calls, self.attempts = max_calls, attempts
        self.circuit_threshold, self.calls, self.temporary_failures = circuit_threshold, 0, 0
        self.call = call or self._gemini_call
        self.cache = json.loads(self.checkpoint.read_text(encoding="utf-8")) if self.checkpoint.exists() else {}

    @staticmethod
    def _gemini_call(prompt):
        from google.genai import types
        # Keep a strong reference for the complete synchronous request. Creating
        # the client inline can let its finalizer close the shared transport.
        client = _client()
        response = client.models.generate_content(
            model="gemini-flash-latest", contents=prompt,
            config=types.GenerateContentConfig(temperature=0, response_mime_type="application/json"),
        )
        return json.loads(response.text)

    def _save(self):
        self.checkpoint.parent.mkdir(parents=True, exist_ok=True)
        self.checkpoint.write_text(json.dumps(self.cache, ensure_ascii=False, indent=2), encoding="utf-8")

    def extract(self, source_id, candidate_windows):
        if source_id in self.cache:
            return self.cache[source_id]
        if self.calls >= self.max_calls:
            return {"status": "SKIPPED_CALL_BUDGET", "observations": []}
        if self.temporary_failures >= self.circuit_threshold:
            return {"status": "CIRCUIT_OPEN", "observations": []}
        # Keep one bounded batch per source. Numeric windows are most useful and
        # bounding the prompt prevents a large report from causing call storms,
        # oversized requests, or repeated 503 failures.
        selected, characters = [], 0
        for window in sorted(candidate_windows, key=lambda x: bool(x.get("numbers")), reverse=True):
            size = len(window.get("text", ""))
            if len(selected) >= 40 or characters + size > 45000:
                break
            selected.append(window); characters += size
        prompt = (
            "Extract financial benchmark observations from the supplied source windows. "
            "Return JSON {observations:[{metric,value,low,high,unit,technology,geography," 
            "statistic,basis,source_excerpt}]}. Never infer a number absent from the text.\n\n" +
            json.dumps(selected, ensure_ascii=False)
        )
        self.calls += 1
        last_error = None
        for attempt in range(self.attempts):
            try:
                result = self.call(prompt)
                payload = {"status": "SUCCESS", "observations": result.get("observations", [])}
                self.cache[source_id] = payload; self._save()
                self.temporary_failures = 0
                return payload
            except Exception as exc:
                last_error = f"{type(exc).__name__}: {exc}"
                classified = classifier_erreur_gemini(exc)
                temporary = isinstance(classified, (GeminiTemporaire, GeminiQuota))
                if not temporary:
                    payload = {"status": "FAILED_PERMANENT", "error": str(exc), "observations": []}
                    self.cache[source_id] = payload; self._save(); return payload
                if attempt + 1 < self.attempts:
                    time.sleep(min(30, 2 ** attempt + random.random()))
        self.temporary_failures += 1
        # Do not cache temporary exhaustion permanently: a later run may retry
        # after the provider recovers. The circuit breaker still stops this run.
        return {"status": "FAILED_TEMPORARY", "error": last_error, "observations": []}
