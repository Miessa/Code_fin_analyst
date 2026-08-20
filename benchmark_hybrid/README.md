# Hybrid benchmark extraction

This subsystem is separate from the active Phase 2 benchmark engine. Its approved
reference file is never overwritten by extraction runs.

## Workflow

```text
official source manifest
  -> resilient download
  -> deterministic PDF/HTML text extraction
  -> keyword windows and numeric candidates
  -> optional one-batch-per-source Gemini structuring
  -> numeric evidence validation
  -> staging/extracted_candidates.json
  -> analyst review
  -> explicit promotion into data/referentiel_normes.json
```

Install dependencies:

```powershell
pip install -r benchmark_hybrid/requirements.txt
```

Code-only extraction:

```powershell
python -m benchmark_hybrid.run_extraction
```

Optional LLM assistance, capped to three calls across the complete run:

```powershell
python -m benchmark_hybrid.run_extraction --use-llm --max-llm-calls 3
```

LLM resilience:

- candidates from one source are sent in one batch;
- successful and failed source results are checkpointed;
- temporary errors including HTTP 503 use bounded exponential backoff;
- two exhausted temporary failures open the circuit breaker;
- a global call budget prevents call storms;
- reruns reuse checkpoints rather than repeat calls;
- LLM values are rejected unless code finds the number in source text.

`data/referentiel_normes.json` separates publication metadata, detailed source
observations, and ARSEL-approved comparison rules. Project observations such as
IRR, tariff, and DSCR remain peer evidence unless ARSEL explicitly promotes them.
