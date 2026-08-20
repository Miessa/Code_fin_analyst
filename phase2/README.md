# Phase 2 — Financial analysis and benchmarks

Phase 2 consumes `hypotheses_validees.json`, the analyst-validated registry written
by Étape 3. It does not read or modify the Excel workbook.

Word output requires `python-docx`:

```powershell
pip install python-docx
```

Run it independently:

```powershell
python run_phase2.py hypotheses_validees.json
```

Outputs are written to `outputs/phase2/` as JSON, Markdown, and Word (`.docx`). The main
`arsel_analyse.py` workflow also starts Phase 2 automatically after Étape 3.

To provide project context used by perimeter checks:

```powershell
python run_phase2.py hypotheses_validees.json --context project_context.json
```

The context may contain `technology`, `geography`, `currency`, and `price_year`.
Only benchmark entries with `approved: true`, compatible units, and complete
required context can produce a verdict. Draft references remain visible as
`NOT_COMPARABLE` and cannot affect the financial opinion.

Copy `phase2_context.example.json` to `phase2_context.json` and complete it for
automatic execution after Étape 3. `usd_per_currency_unit` must be the approved
exchange rate used for the analysis; Phase 2 does not fetch or silently choose an
exchange rate. `monetary_scale` is `1000` when extracted model amounts are in
thousands of currency units.

The supplied reference base currently includes approved reference points from
IRENA's *Renewable Power Generation Costs in 2024* for hydropower, utility-scale
solar PV, and onshore wind. It also contains an IEA solar cost-of-capital point for
South Africa. These are points of comparison, not regulatory pass/fail ranges.
World Bank AREF financing and AfDB Sokodé project observations are retained as
unapproved examples because they are not universal sector norms.

Modules:

- `derived_metrics.py`: auditable derived indicators and formulas.
- `normalization.py`: unit and perimeter comparability controls.
- `benchmark_engine.py`: deterministic range comparison.
- `financial_analysis.py`: deterministic analysis and Markdown restitution.
- `data/referentiel_normes.json`: versioned reference base.
