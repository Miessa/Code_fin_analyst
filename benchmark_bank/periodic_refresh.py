"""Fail-closed periodic source discovery and staging refresh orchestration."""

from __future__ import annotations

import hashlib
import json
import os
import re
import shutil
import tempfile
import uuid
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import urljoin, urlparse
from urllib.request import Request, urlopen

import openpyxl
import pandas as pd

from benchmark_bank.governance import QualityPolicy, refresh_worldbank_bank
from benchmark_bank.sources.irena_tabular import IRENATabularAdapter
from benchmark_bank.sources.worldbank_ppi import REQUIRED_COLUMNS, WorldBankPPIAdapter


WORLD_BANK_PAGE = "https://ppi.worldbank.org/en/ppidata"
WORLD_BANK_FALLBACK = "https://www.worldbank.org/content/dam/PPI/documents/2024-PPI-Full-DTA.dta"
IRENA_PAGE = "https://www.irena.org/Data/View-data-by-topic/Costs/Global-Trends"
IRENA_FALLBACK = "https://www.irena.org/-/media/Files/IRENA/Agency/Publication/2025/Jul/IRENA-Datafile-RenPwrGenCosts-in-2024.xlsx"


class _Links(HTMLParser):
    def __init__(self): super().__init__(); self.links = []
    def handle_starttag(self, tag, attrs):
        if tag.lower() == "a":
            href = dict(attrs).get("href")
            if href: self.links.append(href)


@dataclass(frozen=True)
class RemoteArtifact:
    source: str
    page_url: str
    download_url: str
    final_url: str
    last_modified: str | None
    etag: str | None
    checksum_sha256: str
    size_bytes: int
    data_year: int
    local_path: str | None = None


def _sha256(path):
    digest = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""): digest.update(block)
    return digest.hexdigest()


def _year(text, default):
    years = [int(value) for value in re.findall(r"(?:19|20)\d{2}", text)]
    return max((value for value in years if 1990 <= value <= 2100), default=default)


def _data_year(source, url):
    patterns = ((r"(?:costs|cost)-in-(20\d{2})",) if source == "irena_rpgc"
                else (r"(20\d{2})-ppi", r"ppi[_-](20\d{2})"))
    lowered = url.lower()
    for pattern in patterns:
        match = re.search(pattern, lowered)
        if match: return int(match.group(1))
    return _year(url, 0)


class PeriodicRefreshOrchestrator:
    def __init__(self, *, raw_dir="benchmark_bank/data/raw", staging_path="benchmark_bank/data/staging.duckdb",
                 active_path="benchmark_bank/data/benchmark_bank.duckdb",
                 output_dir="benchmark_bank/outputs/periodic_refresh", manifest_path=None, timeout=120):
        self.raw_dir, self.staging_path, self.active_path = map(Path, (raw_dir, staging_path, active_path))
        self.output_dir = Path(output_dir)
        self.manifest_path = Path(manifest_path) if manifest_path else self.output_dir / "source_manifest.json"
        self.timeout = timeout

    def _request(self, url):
        request = Request(url, headers={"User-Agent": "ARSEL-Benchmark-Bank/1.0"})
        return urlopen(request, timeout=self.timeout)

    def discover(self, source, page_url, fallback_url, suffix):
        candidates = []
        try:
            with self._request(page_url) as response:
                parser = _Links(); parser.feed(response.read().decode("utf-8", errors="ignore"))
            candidates = [urljoin(page_url, link) for link in parser.links
                          if urlparse(link).path.lower().endswith(suffix)]
        except Exception:
            candidates = []
        candidates.append(fallback_url)
        unique = list(dict.fromkeys(candidates))
        return max(unique, key=lambda url: (_year(url, 0), url))

    def download(self, source, page_url, url, destination):
        with self._request(url) as response, Path(destination).open("wb") as stream:
            shutil.copyfileobj(response, stream)
            final_url = response.geturl()
            headers = response.headers
        path = Path(destination)
        if path.stat().st_size < 1024: raise ValueError(f"{source}: downloaded artifact is unexpectedly small")
        return RemoteArtifact(source, page_url, url, final_url, headers.get("Last-Modified"), headers.get("ETag"),
                              _sha256(path), path.stat().st_size,
                              _data_year(source, final_url) or _data_year(source, url))

    @staticmethod
    def validate_worldbank(path):
        with pd.io.stata.StataReader(path) as reader:
            columns = set(reader.variable_labels())
        missing = sorted(REQUIRED_COLUMNS - columns)
        if missing: raise ValueError(f"World Bank PPI columns missing: {missing}")

    @staticmethod
    def validate_irena(path):
        workbook = openpyxl.load_workbook(path, read_only=True, data_only=True)
        try:
            # The adapter is the versioned format contract. A changed workbook fails closed here.
            IRENATabularAdapter(path).build_from_workbook(workbook, checksum=_sha256(path))
        finally: workbook.close()

    def _load_manifest(self):
        if not self.manifest_path.exists(): return {"sources": {}}
        return json.loads(self.manifest_path.read_text(encoding="utf-8"))

    @staticmethod
    def _current_manifest_entry(record):
        """Read both the legacy flat manifest and the content-addressed format."""
        if not isinstance(record, dict): return {}
        return record.get("current") or record

    def persist_snapshot(self, downloaded_path, artifact, suffix):
        """Atomically create a content-addressed snapshot without ever replacing one."""
        downloaded_path = Path(downloaded_path)
        actual = _sha256(downloaded_path)
        if actual != artifact.checksum_sha256:
            raise ValueError(f"{artifact.source}: checksum changed between download and snapshot")
        directory = self.raw_dir / artifact.source / str(artifact.data_year)
        directory.mkdir(parents=True, exist_ok=True)
        target = directory / f"{artifact.checksum_sha256}{suffix}"
        if target.exists():
            if _sha256(target) != artifact.checksum_sha256:
                raise ValueError(f"{artifact.source}: immutable snapshot checksum mismatch at {target}")
            return target, False
        partial = directory / f".{artifact.checksum_sha256}.{uuid.uuid4().hex}.partial"
        try:
            shutil.copy2(downloaded_path, partial)
            if _sha256(partial) != artifact.checksum_sha256:
                raise ValueError(f"{artifact.source}: temporary snapshot checksum mismatch")
            try:
                os.link(partial, target)  # atomic and fails if another process created target
                created = True
            except FileExistsError:
                created = False
            if _sha256(target) != artifact.checksum_sha256:
                raise ValueError(f"{artifact.source}: immutable snapshot checksum mismatch at {target}")
            return target, created
        finally:
            partial.unlink(missing_ok=True)

    def run(self):
        started = datetime.now(timezone.utc)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        report = {"schema_version":"1.0.0", "started_at":started.isoformat(), "status":"failed",
                  "promotion_requested":False, "promotion_performed":False, "sources":{}, "error":None}
        try:
            urls = {
                "worldbank_ppi": self.discover("worldbank_ppi", WORLD_BANK_PAGE, WORLD_BANK_FALLBACK, ".dta"),
                "irena_rpgc": self.discover("irena_rpgc", IRENA_PAGE, IRENA_FALLBACK, ".xlsx"),
            }
            previous_manifest = self._load_manifest()
            previous = previous_manifest.get("sources", {})
            with tempfile.TemporaryDirectory(prefix="arsel_benchmark_refresh_") as temporary:
                temporary = Path(temporary)
                wb = self.download("worldbank_ppi", WORLD_BANK_PAGE, urls["worldbank_ppi"], temporary / "worldbank.dta")
                irena = self.download("irena_rpgc", IRENA_PAGE, urls["irena_rpgc"], temporary / "irena.xlsx")
                self.validate_worldbank(temporary / "worldbank.dta")
                if irena.data_year != 2024:
                    raise ValueError(
                        f"IRENA edition {irena.data_year} detected but no reviewed extraction mapping exists; "
                        "staging was not rebuilt"
                    )
                self.validate_irena(temporary / "irena.xlsx")
                wb_path, wb_created = self.persist_snapshot(temporary / "worldbank.dta", wb, ".dta")
                irena_path, irena_created = self.persist_snapshot(temporary / "irena.xlsx", irena, ".xlsx")
                wb = RemoteArtifact(**{**asdict(wb), "local_path":str(wb_path)})
                irena = RemoteArtifact(**{**asdict(irena), "local_path":str(irena_path)})
            created_by_source = {"worldbank_ppi":wb_created, "irena_rpgc":irena_created}
            for artifact in (wb, irena):
                item = asdict(artifact)
                old = self._current_manifest_entry(previous.get(artifact.source, {}))
                item["changed"] = old.get("checksum_sha256") != artifact.checksum_sha256
                item["validated"] = True
                item["snapshot_created"] = created_by_source[artifact.source]
                report["sources"][artifact.source] = item
            if any(item["changed"] for item in report["sources"].values()):
                governance = refresh_worldbank_bank(
                    wb.local_path, staging_path=self.staging_path, active_path=self.active_path,
                    output_dir=self.output_dir / "governance", recent_from=2020,
                    policy=QualityPolicy(minimum_sector_statistics=20), promote=False,
                    irena_artifact_path=irena.local_path,
                )
                report["governance"] = governance
                report["status"] = "staging_ready" if governance["quality"]["passed"] else "quality_failed"
            else:
                report["governance"] = None
                report["status"] = "no_change"
            manifest_sources = {}
            now = datetime.now(timezone.utc).isoformat()
            for source, current in report["sources"].items():
                old_record = previous.get(source, {})
                history = list(old_record.get("snapshots", [])) if isinstance(old_record, dict) else []
                old_current = self._current_manifest_entry(old_record)
                if not history and old_current.get("checksum_sha256"):
                    history.append(old_current)
                snapshot = {key:value for key,value in current.items()
                            if key not in {"changed", "validated", "snapshot_created"}}
                snapshot["first_seen_at"] = now
                existing = next((item for item in history
                                 if item.get("checksum_sha256") == snapshot["checksum_sha256"]), None)
                if existing:
                    snapshot["first_seen_at"] = existing.get("first_seen_at", now)
                    history[history.index(existing)] = snapshot
                else:
                    history.append(snapshot)
                manifest_sources[source] = {"current":snapshot, "snapshots":history}
            manifest = {"schema_version":"2.0.0", "updated_at":now, "sources":manifest_sources}
            self.manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
        except Exception as exc:
            report["error"] = {"type":type(exc).__name__, "message":str(exc)}
        report["completed_at"] = datetime.now(timezone.utc).isoformat()
        (self.output_dir / "periodic_refresh_report.json").write_text(
            json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
        return report
