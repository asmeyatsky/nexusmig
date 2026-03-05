"""
Export Quarantine Command Tests
"""
import csv
import json
import tempfile
from pathlib import Path

from application.commands.export_quarantine import ExportQuarantineCommand
from domain.value_objects.migration_result import (
    BatchResult, MigrationSummary, RecordResult, RecordStatus,
)


def _summary_with_quarantined() -> MigrationSummary:
    return MigrationSummary(
        batches=(BatchResult(
            object_type="Account", total=5, success_count=3,
            warning_count=0, error_count=0, quarantined_count=2,
            record_results=(
                RecordResult(salesforce_id="001A", object_type="Account",
                            status=RecordStatus.SUCCESS),
                RecordResult(salesforce_id="001B", object_type="Account",
                            status=RecordStatus.QUARANTINED, message="Name is required"),
                RecordResult(salesforce_id="001C", object_type="Account",
                            status=RecordStatus.QUARANTINED, message="Duplicate detected"),
            ),
        ),),
        total_extracted=5, total_loaded=3, total_quarantined=2,
    )


class TestExportQuarantine:
    def test_export_csv(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            path = ExportQuarantineCommand(
                summary=_summary_with_quarantined(),
                output_dir=tmpdir, fmt="csv",
            ).execute()

            assert Path(path).exists()
            with open(path) as f:
                rows = list(csv.DictReader(f))
            assert len(rows) == 2
            assert rows[0]["salesforce_id"] == "001B"
            assert rows[0]["reason"] == "Name is required"

    def test_export_json(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            path = ExportQuarantineCommand(
                summary=_summary_with_quarantined(),
                output_dir=tmpdir, fmt="json",
            ).execute()

            data = json.loads(Path(path).read_text())
            assert len(data) == 2
            assert data[1]["salesforce_id"] == "001C"

    def test_no_quarantined_records(self):
        summary = MigrationSummary(
            batches=(BatchResult(
                object_type="Account", total=5, success_count=5,
                warning_count=0, error_count=0, quarantined_count=0,
            ),),
            total_extracted=5, total_loaded=5,
        )
        with tempfile.TemporaryDirectory() as tmpdir:
            path = ExportQuarantineCommand(
                summary=summary, output_dir=tmpdir, fmt="csv",
            ).execute()
            with open(path) as f:
                rows = list(csv.DictReader(f))
            assert len(rows) == 0
