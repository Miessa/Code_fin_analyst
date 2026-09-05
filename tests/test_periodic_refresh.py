import tempfile
import unittest
import json
import hashlib
from pathlib import Path
from unittest.mock import patch

from benchmark_bank.periodic_refresh import PeriodicRefreshOrchestrator, RemoteArtifact, _data_year


CONTENT = b"x" * 2048
CHECKSUM = hashlib.sha256(CONTENT).hexdigest()


class FakeOrchestrator(PeriodicRefreshOrchestrator):
    irena_year = 2024

    def discover(self, source, page_url, fallback_url, suffix):
        return fallback_url

    def download(self, source, page_url, url, destination):
        path = Path(destination)
        path.write_bytes(CONTENT)
        year = 2024 if source == "worldbank_ppi" else self.irena_year
        return RemoteArtifact(source, page_url, url, url, None, None, CHECKSUM, 2048, year)

    @staticmethod
    def validate_worldbank(path): pass

    @staticmethod
    def validate_irena(path): pass


class PeriodicRefreshTests(unittest.TestCase):
    def test_data_year_uses_dataset_year_not_publication_year(self):
        url = "https://example/Publication/2025/Jul/IRENA-Datafile-RenPwrGenCosts-in-2024.xlsx"
        self.assertEqual(_data_year("irena_rpgc", url), 2024)
        self.assertEqual(_data_year("worldbank_ppi", "https://example/2024-PPI-Full-DTA.dta"), 2024)

    def test_success_rebuilds_staging_without_promotion(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            governance = {"quality":{"passed":True}}
            with patch("benchmark_bank.periodic_refresh.refresh_worldbank_bank", return_value=governance) as refresh:
                report = FakeOrchestrator(raw_dir=root/"raw", staging_path=root/"staging.duckdb",
                    active_path=root/"active.duckdb", output_dir=root/"out").run()
            self.assertEqual(report["status"], "staging_ready")
            self.assertFalse(report["promotion_performed"])
            self.assertFalse(refresh.call_args.kwargs["promote"])
            self.assertTrue((root/"out"/"source_manifest.json").exists())
            snapshots = list((root/"raw"/"worldbank_ppi"/"2024").glob("*.dta"))
            self.assertEqual([path.stem for path in snapshots], [CHECKSUM])

    def test_unknown_irena_edition_fails_before_staging_rebuild(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            orchestrator = FakeOrchestrator(raw_dir=root/"raw", staging_path=root/"staging.duckdb",
                active_path=root/"active.duckdb", output_dir=root/"out")
            orchestrator.irena_year = 2025
            with patch("benchmark_bank.periodic_refresh.refresh_worldbank_bank") as refresh:
                report = orchestrator.run()
            self.assertEqual(report["status"], "failed")
            self.assertIn("no reviewed extraction mapping", report["error"]["message"])
            refresh.assert_not_called()
            self.assertFalse((root/"staging.duckdb").exists())

    def test_unchanged_checksums_skip_staging_rebuild(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory); output = root/"out"; output.mkdir()
            (output/"source_manifest.json").write_text(json.dumps({"sources": {
                "worldbank_ppi":{"checksum_sha256":CHECKSUM},
                "irena_rpgc":{"checksum_sha256":CHECKSUM},
            }}), encoding="utf-8")
            with patch("benchmark_bank.periodic_refresh.refresh_worldbank_bank") as refresh:
                report = FakeOrchestrator(raw_dir=root/"raw", staging_path=root/"staging.duckdb",
                    active_path=root/"active.duckdb", output_dir=output).run()
            self.assertEqual(report["status"], "no_change")
            refresh.assert_not_called()

    def test_existing_snapshot_is_never_overwritten(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            orchestrator = FakeOrchestrator(raw_dir=root/"raw", output_dir=root/"out")
            downloaded = root/"download.dta"; downloaded.write_bytes(CONTENT)
            artifact = RemoteArtifact("worldbank_ppi", "page", "url", "url", None, None,
                                      CHECKSUM, len(CONTENT), 2024)
            target, created = orchestrator.persist_snapshot(downloaded, artifact, ".dta")
            self.assertTrue(created)
            target.write_bytes(b"corrupted")
            with self.assertRaisesRegex(ValueError, "immutable snapshot checksum mismatch"):
                orchestrator.persist_snapshot(downloaded, artifact, ".dta")
            self.assertEqual(target.read_bytes(), b"corrupted")

    def test_manifest_keeps_snapshot_history(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            governance = {"quality":{"passed":True}}
            with patch("benchmark_bank.periodic_refresh.refresh_worldbank_bank", return_value=governance):
                FakeOrchestrator(raw_dir=root/"raw", staging_path=root/"staging.duckdb",
                    active_path=root/"active.duckdb", output_dir=root/"out").run()
            manifest = json.loads((root/"out"/"source_manifest.json").read_text(encoding="utf-8"))
            self.assertEqual(manifest["schema_version"], "2.0.0")
            self.assertEqual(len(manifest["sources"]["worldbank_ppi"]["snapshots"]), 1)
            self.assertEqual(manifest["sources"]["worldbank_ppi"]["current"]["checksum_sha256"], CHECKSUM)

    def test_legacy_manifest_path_is_migrated_even_when_checksum_is_unchanged(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory); output = root/"out"; output.mkdir()
            legacy = root/"raw"/"worldbank_ppi_2024.dta"
            (output/"source_manifest.json").write_text(json.dumps({"sources": {
                "worldbank_ppi":{"checksum_sha256":CHECKSUM, "local_path":str(legacy)},
                "irena_rpgc":{"checksum_sha256":CHECKSUM, "local_path":str(root/"raw"/"irena_rpgc_2024.xlsx")},
            }}), encoding="utf-8")
            with patch("benchmark_bank.periodic_refresh.refresh_worldbank_bank") as refresh:
                FakeOrchestrator(raw_dir=root/"raw", staging_path=root/"staging.duckdb",
                    active_path=root/"active.duckdb", output_dir=output).run()
            refresh.assert_not_called()
            manifest = json.loads((output/"source_manifest.json").read_text(encoding="utf-8"))
            current = manifest["sources"]["worldbank_ppi"]["current"]
            self.assertEqual(Path(current["local_path"]).stem, CHECKSUM)
            self.assertNotEqual(Path(current["local_path"]), legacy)


if __name__ == "__main__": unittest.main()
