"""
Log Reader Tests
"""
import json
import pytest
import tempfile
from pathlib import Path

from infrastructure.logging.log_reader import LogReader
from infrastructure.logging.migration_logger import MigrationLogger
from domain.value_objects.migration_result import (
    BatchResult, MigrationSummary, RecordResult, RecordStatus,
)


def _sample_summary() -> MigrationSummary:
    return MigrationSummary(
        batches=(
            BatchResult(
                object_type="Account", total=3, success_count=2,
                warning_count=0, error_count=0, quarantined_count=1,
                record_results=(
                    RecordResult(salesforce_id="001A", object_type="companies",
                                status=RecordStatus.SUCCESS, nexus_id="n1"),
                    RecordResult(salesforce_id="001B", object_type="companies",
                                status=RecordStatus.SUCCESS, nexus_id="n2"),
                    RecordResult(salesforce_id="001C", object_type="Account",
                                status=RecordStatus.QUARANTINED, message="Name is required"),
                ),
            ),
        ),
        total_extracted=3, total_loaded=2, total_quarantined=1,
        duration_seconds=1.5,
        warnings=("Unresolved reference: 001X",),
    )


class TestLogReader:
    def test_round_trip_write_and_read(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            logger = MigrationLogger(log_dir=tmpdir)
            original = _sample_summary()
            log_path = logger.write_summary(original)

            reader = LogReader()
            restored = reader.read_summary(log_path)

            assert restored.total_extracted == original.total_extracted
            assert restored.total_loaded == original.total_loaded
            assert restored.total_quarantined == original.total_quarantined
            assert restored.duration_seconds == original.duration_seconds
            assert len(restored.batches) == 1
            assert restored.batches[0].object_type == "Account"
            assert restored.batches[0].total == 3
            assert restored.batches[0].quarantined_count == 1
            assert "Unresolved reference: 001X" in restored.warnings

    def test_record_statuses_preserved(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            logger = MigrationLogger(log_dir=tmpdir)
            log_path = logger.write_summary(_sample_summary())

            reader = LogReader()
            restored = reader.read_summary(log_path)

            records = restored.batches[0].record_results
            statuses = {r.status for r in records}
            assert RecordStatus.SUCCESS in statuses
            assert RecordStatus.QUARANTINED in statuses

    def test_file_not_found_raises(self):
        reader = LogReader()
        with pytest.raises(FileNotFoundError):
            reader.read_summary("/nonexistent/log.jsonl")

    def test_find_latest_log(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            # Create two log files
            (Path(tmpdir) / "migration_20240101_000000.jsonl").write_text("{}\n")
            (Path(tmpdir) / "migration_20240102_000000.jsonl").write_text("{}\n")

            reader = LogReader()
            latest = reader.find_latest_log(tmpdir)
            assert "20240102" in latest

    def test_list_logs(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            (Path(tmpdir) / "migration_20240101_000000.jsonl").write_text("{}\n")
            (Path(tmpdir) / "migration_20240102_000000.jsonl").write_text("{}\n")
            (Path(tmpdir) / "other_file.txt").write_text("ignore\n")

            reader = LogReader()
            logs = reader.list_logs(tmpdir)
            assert len(logs) == 2

    def test_find_latest_empty_dir(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            reader = LogReader()
            assert reader.find_latest_log(tmpdir) is None
