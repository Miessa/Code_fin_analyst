"""Hybrid workflow: download -> code extraction -> optional LLM -> validation -> staging."""

import json
from datetime import datetime, timezone
from pathlib import Path

from .code_extractor import candidate_windows, extract_text
from .downloader import download
from .llm_extractor import ResilientLLMExtractor
from .validator import validate_observation


ROOT = Path(__file__).resolve().parent


class HybridBenchmarkPipeline:
    def __init__(self, manifest=ROOT / "data/sources.json", workdir=ROOT / "work"):
        self.manifest_path, self.workdir = Path(manifest), Path(workdir)
        self.manifest = json.loads(self.manifest_path.read_text(encoding="utf-8"))

    def run(self, use_llm=False, max_llm_calls=3):
        staged = {"generated_at": datetime.now(timezone.utc).isoformat(), "sources": []}
        llm = ResilientLLMExtractor(self.workdir / "checkpoints/llm.json", max_calls=max_llm_calls)
        for source in self.manifest["sources"]:
            suffix = ".pdf" if ".pdf" in source["url"].lower() else ".html"
            local = self.workdir / "downloads" / f"{source['source_id']}{suffix}"
            record = {"source_id": source["source_id"], "status": None, "code_candidates": [], "llm": None}
            try:
                if not local.exists():
                    download(source["url"], local)
                text = extract_text(local)
                windows = candidate_windows(text, source.get("keywords", []))
                record["code_candidates"] = windows
                if use_llm and windows:
                    result = llm.extract(source["source_id"], windows)
                    for observation in result.get("observations", []):
                        observation["validation"] = validate_observation(observation, text)
                        observation["approval_status"] = "pending_analyst"
                    record["llm"] = result
                record["status"] = "EXTRACTED"
            except Exception as exc:
                record.update(status="FAILED", error=f"{type(exc).__name__}: {exc}")
            staged["sources"].append(record)
        destination = self.workdir / "staging/extracted_candidates.json"
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_text(json.dumps(staged, ensure_ascii=False, indent=2), encoding="utf-8")
        return staged, destination
