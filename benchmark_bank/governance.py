"""Staging, quality gates, change detection and controlled bank promotion."""

from __future__ import annotations

import json
import shutil
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path

from benchmark_bank.analytics import build_project_features
from benchmark_bank.sources import IRENATabularAdapter, WorldBankPPIAdapter
from benchmark_bank.storage import BenchmarkRepository


@dataclass(frozen=True)
class QualityPolicy:
    minimum_energy_projects: int = 1000
    minimum_recent_eligible_projects: int = 100
    minimum_investment_per_mw_coverage: float = 0.50
    maximum_ambiguous_investment_share: float = 0.20
    maximum_project_removal_share: float = 0.10
    minimum_sector_statistics: int = 0


def database_snapshot(path):
    path = Path(path)
    if not path.exists(): return {}
    with BenchmarkRepository(path, read_only=True) as repository:
        result = {}
        for entity, table, id_field in (
            ("source", "current_sources", "source_id"),
            ("project", "current_projects", "project_id"),
            ("observation", "current_observations", "observation_id"),
        ):
            result[entity] = dict(repository.connection.execute(
                f"SELECT {id_field}, content_hash FROM {table}"
            ).fetchall())
        return result


def compare_snapshots(active, staging):
    changes = {}
    for entity in sorted(set(active) | set(staging)):
        old, new = active.get(entity, {}), staging.get(entity, {})
        changes[entity] = {
            "added": sorted(set(new) - set(old)), "removed": sorted(set(old) - set(new)),
            "modified": sorted(key for key in set(old) & set(new) if old[key] != new[key]),
            "unchanged_count": sum(old[key] == new[key] for key in set(old) & set(new)),
        }
    return changes


def assess_quality(ingestion_report, features, changes, policy=QualityPolicy(), sector_statistics_count=0,
                   expected_project_removals=None):
    total = len(features)
    available = sum(item.investment_per_mw_usd is not None for item in features)
    ambiguous = sum(any(
        issue.code == "ambiguous_multiple_values" and issue.field == "investment_commitment"
        for issue in item.issues
    ) for item in features)
    active_projects = changes.get("project", {}).get("unchanged_count", 0) + len(
        changes.get("project", {}).get("removed", [])
    ) + len(changes.get("project", {}).get("modified", []))
    removed_ids = set(changes.get("project", {}).get("removed", []))
    expected_removed_ids = removed_ids & set(expected_project_removals or [])
    unexpected_removed_ids = removed_ids - expected_removed_ids
    removed = len(unexpected_removed_ids)
    measures = {
        "energy_project_count": total,
        "recent_eligible_project_count": ingestion_report.default_eligible_projects,
        "investment_per_mw_coverage": available / total if total else 0,
        "ambiguous_investment_share": ambiguous / total if total else 1,
        "project_removal_share": removed / active_projects if active_projects else 0,
        "intentional_project_exclusions": len(expected_removed_ids),
        "unexpected_project_removals": len(unexpected_removed_ids),
        "sector_statistics_count": sector_statistics_count,
    }
    gates = [
        {"gate": "minimum_energy_projects", "passed": total >= policy.minimum_energy_projects,
         "actual": total, "threshold": policy.minimum_energy_projects},
        {"gate": "minimum_recent_eligible_projects",
         "passed": ingestion_report.default_eligible_projects >= policy.minimum_recent_eligible_projects,
         "actual": ingestion_report.default_eligible_projects,
         "threshold": policy.minimum_recent_eligible_projects},
        {"gate": "minimum_investment_per_mw_coverage",
         "passed": measures["investment_per_mw_coverage"] >= policy.minimum_investment_per_mw_coverage,
         "actual": measures["investment_per_mw_coverage"],
         "threshold": policy.minimum_investment_per_mw_coverage},
        {"gate": "maximum_ambiguous_investment_share",
         "passed": measures["ambiguous_investment_share"] <= policy.maximum_ambiguous_investment_share,
         "actual": measures["ambiguous_investment_share"],
         "threshold": policy.maximum_ambiguous_investment_share},
        {"gate": "maximum_project_removal_share",
         "passed": measures["project_removal_share"] <= policy.maximum_project_removal_share,
         "actual": measures["project_removal_share"],
         "threshold": policy.maximum_project_removal_share},
        {"gate": "minimum_sector_statistics",
         "passed": sector_statistics_count >= policy.minimum_sector_statistics,
         "actual": sector_statistics_count, "threshold": policy.minimum_sector_statistics},
    ]
    issue_counts = {}
    for item in features:
        for issue in item.issues: issue_counts[issue.code] = issue_counts.get(issue.code, 0) + 1
    return {"passed": all(gate["passed"] for gate in gates), "policy": asdict(policy),
            "measures": measures, "gates": gates, "quality_issue_counts": issue_counts,
            "filters": {
                "source_sector": "Energy only",
                "technology_policy": "projects without a classified technology are intentionally excluded",
                "default_cohort": "financial close >= 2020 and status not Cancelled/Distressed/Concluded",
                "historical_policy": "older energy projects retained only as controlled fallback",
                "feature_policy": "zero, negative, missing and ambiguous values excluded metric-by-metric",
                "plausibility_ranges": {
                    "capacity_mw": [0.1, 20000], "investment_per_kw_usd": [50, 30000],
                    "contract_period_years": [1, 100], "private_ownership_share": [0.000001, 1],
                },
            }}


def promote_staging(staging_path, active_path, backup_dir):
    staging_path, active_path, backup_dir = map(Path, (staging_path, active_path, backup_dir))
    if not staging_path.exists(): raise FileNotFoundError(staging_path)
    backup_dir.mkdir(parents=True, exist_ok=True)
    backup = None
    if active_path.exists():
        stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        backup = backup_dir / f"benchmark_bank_{stamp}.duckdb"
        shutil.copy2(active_path, backup)
    active_path.parent.mkdir(parents=True, exist_ok=True)
    temporary = active_path.with_suffix(".promotion.tmp")
    shutil.copy2(staging_path, temporary)
    temporary.replace(active_path)
    return backup


def refresh_worldbank_bank(artifact_path, *, staging_path, active_path,
                           output_dir, recent_from=2020, policy=QualityPolicy(), promote=False,
                           irena_artifact_path=None):
    staging_path, active_path, output_dir = map(Path, (staging_path, active_path, output_dir))
    output_dir.mkdir(parents=True, exist_ok=True)
    if staging_path.exists(): staging_path.unlink()
    document, ingestion_report = WorldBankPPIAdapter(
        artifact_path, recent_from_year=recent_from
    ).build()
    with BenchmarkRepository(staging_path) as repository:
        repository.load_document(document)
        irena_report = None
        if irena_artifact_path:
            irena_document, irena_report = IRENATabularAdapter(irena_artifact_path).build()
            repository.load_document(irena_document)
        features = build_project_features(repository)
        staging_counts = repository.counts()
        sector_statistics_count = repository.connection.execute(
            "SELECT count(*) FROM current_observations WHERE observation_type = 'sector_statistic'"
        ).fetchone()[0]
    changes = compare_snapshots(database_snapshot(active_path), database_snapshot(staging_path))
    expected_project_removals = set()
    if active_path.exists():
        with BenchmarkRepository(active_path, read_only=True) as repository:
            expected_project_removals = {
                row[0] for row in repository.connection.execute(
                    "SELECT project_id FROM current_projects WHERE technology IS NULL"
                ).fetchall()
            }
    quality = assess_quality(
        ingestion_report, features, changes, policy,
        sector_statistics_count=sector_statistics_count,
        expected_project_removals=expected_project_removals,
    )
    promoted, backup = False, None
    if promote:
        if not quality["passed"]:
            raise RuntimeError("Quality gates failed; staging bank was not promoted")
        backup = promote_staging(staging_path, active_path, active_path.parent / "backups")
        promoted = True
    report = {
        "schema_version": "1.0.0", "generated_at": datetime.now(timezone.utc).isoformat(),
        "status": "promoted" if promoted else "staging_ready" if quality["passed"] else "quality_failed",
        "source_ingestion": ingestion_report.model_dump(mode="json"),
        "irena_ingestion": irena_report.model_dump(mode="json") if irena_report else None,
        "staging_counts": staging_counts, "quality": quality,
        "promotion": {"requested": promote, "performed": promoted,
                      "backup_path": str(backup.resolve()) if backup else None},
    }
    (output_dir / "update_report.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    (output_dir / "change_log.json").write_text(
        json.dumps(changes, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    (output_dir / "quality_dashboard.json").write_text(
        json.dumps(quality, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    return report
