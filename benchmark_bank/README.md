# ARSEL Benchmark Bank

This package contains the canonical, versioned data contracts for the future
project-level benchmark bank. It is intentionally independent of Phase 1,
Phase 2 and source-specific extraction code.

The primary entities are:

- `Source`: publication and licensing provenance;
- `Project`: stable project identity and categorical attributes;
- `Observation`: an atomic metric with raw evidence, normalized value and
  economic perimeter;
- `IngestionRun`: immutable execution metadata for a source adapter;
- `NormalizationEvent`: field-level transformation lineage;
- `BenchmarkBankDocument`: an exchange format that validates identifiers and
  cross-references between all entities.

Missing benchmark fields remain `null`. Unknown values must never be inferred
merely to satisfy the schema.

Generate portable JSON Schema files with:

```powershell
python -m benchmark_bank.schemas.export
```

The generated JSON files are contracts and exchange artifacts. Step 2 will use
the same models to create the DuckDB storage layer.

## DuckDB repository

Initialize or migrate the local database with:

```powershell
python -m benchmark_bank.cli.init_db
```

The repository stores selected fields in typed columns for fast queries and
retains the complete validated JSON payload for reconstruction. Logical updates
create append-only revisions; identical reruns do not create duplicate records.

```python
from benchmark_bank.storage import BenchmarkRepository

with BenchmarkRepository() as bank:
    bank.upsert_source(source)
    bank.upsert_project(project)
    projects = bank.query_projects(
        technology="hydropower",
        region="Sub-Saharan Africa",
    )
```

The generated `benchmark_bank/data/*.duckdb` database and its write-ahead log
are local runtime artifacts and are excluded from Git.

## World Bank PPI adapter

The first source adapter reads the official World Bank PPI STATA dataset. It
imports only energy-sector projects into the canonical bank. Projects with a
financial closure year from 2020 onward are marked as the default recent cohort;
older energy projects remain available for controlled fallback. Cancelled,
distressed and concluded projects are retained as evidence but are not default
comparables.

```powershell
python -m benchmark_bank.cli.ingest_worldbank_ppi `
  benchmark_bank/data/raw/worldbank_ppi_2024.dta
```

PPI investment fields are stored as investment commitments in current USD.
They are not relabelled as executed CAPEX or construction cost. Repeated project
rows are consolidated by the official World Bank project ID, while distinct
investment years, technologies, capacities and funding observations remain
separate source-backed observations.

## Analytical layer

Step 4 derives conservative, project-level features and quality flags. A value
is not aggregated when a project has several distinct source values and the
source does not provide an unambiguous aggregation rule. This prevents a
plausible-looking but economically unsupported investment-per-MW ratio.

```powershell
python -m benchmark_bank.cli.build_analytical_layer
```

The resulting `benchmark_bank/outputs/project_features.json` includes usable
investment, capacity, investment/MW, capital structure and contract-period
features, their source observation IDs, quality issues and default-cohort
eligibility. `benchmark_bank.analytics.rank_comparables` then applies a hard
technology filter, a 0.2x–5x capacity band, and explainable geography, capacity, date and contract-period
scores. Statistics are metric-specific and always retain their sample size.

Given a target profile JSON, generate a candidate shortlist with:

```powershell
python -m benchmark_bank.cli.find_comparables project_profile.json
```

The output is explicitly labelled as unapproved. Its preliminary distributions
must not enter the regulatory report until the analyst has approved the project
IDs in a later workflow step.

## Analyst-approved comparable selection

Step 5 builds a generic `projet_analyse` profile from Phase 1 and Phase 2
context, ranks candidates and keeps the analyst in control:

```powershell
python -m benchmark_bank.cli.select_comparables hypotheses_validees.json
```

The interactive commands approve, reject, inspect, skip, go back or stop.
Invalid commands do not advance. Decisions and metric-specific statistics based
only on approved projects are written to
`outputs/phase2/comparable_selection.json`. The file remains separate from the
validated project assumptions to preserve the audit boundary.

## Resumable end-to-end orchestration

After Phase 1 validation, `arsel_analyse.py` invokes the resumable orchestrator.
To resume without reopening Excel, run:

```powershell
python run_analysis.py hypotheses_validees.json
```

It checks registry, context, project-profile and benchmark-bank fingerprints
before reusing a comparable selection. It writes
`outputs/phase2/analysis_manifest.json` with stage status, absolute artifact
paths, SHA-256 checksums and report outputs.

## Controlled bank refresh

Step 8 always builds a staging bank first:

```powershell
python -m benchmark_bank.cli.refresh_bank benchmark_bank/data/raw/worldbank_ppi_2024.dta
```

It reports energy-sector filtering, recent/default eligibility, metric coverage,
ambiguous values and project removals. `--promote` replaces the active bank only
when every quality gate passes and creates a timestamped backup first.

When `benchmark_bank/data/raw/irena_rpgc_2024.xlsx` is present, the refresh
command also rebuilds IRENA sector statistics directly from the official
tabular datafile. These remain
`observation_type=sector_statistic` and are never mixed with PPI project rows.

## Periodic source refresh

The network orchestrator discovers the official World Bank PPI and IRENA
tabular artifacts, downloads them into a temporary directory, validates their
format, stores checksum-versioned provenance, and rebuilds staging only:

```powershell
python -m benchmark_bank.cli.periodic_refresh
```

It never promotes the active bank. World Bank projects without a classified
technology are rejected by the source adapter on every run. A new IRENA edition
whose year or workbook layout has no reviewed extraction mapping fails closed
before staging is touched. The machine-readable execution report and source
manifest are written under `benchmark_bank/outputs/periodic_refresh/`.

Validated raw artifacts are immutable, content-addressed snapshots:

```text
benchmark_bank/data/raw/<source>/<data-year>/<sha256>.<extension>
```

The orchestrator creates a snapshot atomically and never overwrites an existing
checksum path. If an existing file no longer matches its checksum, the refresh
fails closed. `source_manifest.json` version 2 retains the current snapshot and
the complete per-source snapshot history, including URL, ETag, Last-Modified,
download size and first-seen timestamp.

Use Windows Task Scheduler, cron, or another external scheduler to invoke this
command at the desired frequency. A non-zero exit status means discovery,
validation, ingestion, or a quality gate failed and requires review.
