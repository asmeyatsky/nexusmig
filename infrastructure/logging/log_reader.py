"""
Migration Log Reader

Architectural Intent:
- Infrastructure concern: reconstructs a MigrationSummary from a JSONL log file
- Inverse of MigrationLogger.write_summary
- Enables report generation from historical runs without re-executing
"""
import json
from pathlib import Path

from domain.value_objects.migration_result import (
    BatchResult,
    MigrationSummary,
    RecordResult,
    RecordStatus,
)


class LogReader:
    def read_summary(self, log_path: str) -> MigrationSummary:
        path = Path(log_path)
        if not path.exists():
            raise FileNotFoundError(f"Log file not found: {log_path}")

        batches: list[BatchResult] = []
        current_batch_meta: dict | None = None
        current_records: list[RecordResult] = []
        summary_data: dict = {}

        with open(path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                entry = json.loads(line)
                entry_type = entry.get("type")

                if entry_type == "batch":
                    # Flush previous batch
                    if current_batch_meta is not None:
                        batches.append(self._build_batch(current_batch_meta, current_records))
                    current_batch_meta = entry
                    current_records = []

                elif entry_type == "record":
                    current_records.append(RecordResult(
                        salesforce_id=entry.get("salesforce_id", ""),
                        object_type=entry.get("object_type", ""),
                        status=RecordStatus(entry.get("status", "success")),
                        nexus_id=entry.get("nexus_id", "") or None,
                        message=entry.get("message", ""),
                    ))

                elif entry_type == "summary":
                    summary_data = entry

        # Flush last batch
        if current_batch_meta is not None:
            batches.append(self._build_batch(current_batch_meta, current_records))

        # Fallback: if no batch metadata, group records by object_type
        if not batches and current_records:
            batches = self._batches_from_records(current_records)

        return MigrationSummary(
            batches=tuple(batches),
            total_extracted=summary_data.get("total_extracted", 0),
            total_loaded=summary_data.get("total_loaded", 0),
            total_quarantined=summary_data.get("total_quarantined", 0),
            duration_seconds=summary_data.get("duration_seconds", 0.0),
            warnings=tuple(summary_data.get("warnings", [])),
        )

    @staticmethod
    def _build_batch(meta: dict, records: list[RecordResult]) -> BatchResult:
        return BatchResult(
            object_type=meta.get("object_type", ""),
            total=meta.get("total", len(records)),
            success_count=meta.get("success_count", 0),
            warning_count=meta.get("warning_count", 0),
            error_count=meta.get("error_count", 0),
            quarantined_count=meta.get("quarantined_count", 0),
            record_results=tuple(records),
        )

    @staticmethod
    def _batches_from_records(records: list[RecordResult]) -> list[BatchResult]:
        from collections import defaultdict
        by_type: dict[str, list[RecordResult]] = defaultdict(list)
        for r in records:
            by_type[r.object_type].append(r)

        batches = []
        for obj_type, recs in by_type.items():
            batches.append(BatchResult(
                object_type=obj_type,
                total=len(recs),
                success_count=sum(1 for r in recs if r.status == RecordStatus.SUCCESS),
                warning_count=sum(1 for r in recs if r.status == RecordStatus.WARNING),
                error_count=sum(1 for r in recs if r.status == RecordStatus.ERROR),
                quarantined_count=sum(1 for r in recs if r.status == RecordStatus.QUARANTINED),
                record_results=tuple(recs),
            ))
        return batches

    def find_latest_log(self, log_dir: str = "./logs") -> str | None:
        log_path = Path(log_dir)
        if not log_path.exists():
            return None
        logs = sorted(log_path.glob("migration_*.jsonl"), reverse=True)
        return str(logs[0]) if logs else None

    def list_logs(self, log_dir: str = "./logs") -> list[str]:
        log_path = Path(log_dir)
        if not log_path.exists():
            return []
        return [str(p) for p in sorted(log_path.glob("migration_*.jsonl"), reverse=True)]
