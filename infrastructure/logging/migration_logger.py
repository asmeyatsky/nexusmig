"""
Migration Logger

Architectural Intent:
- Infrastructure concern for structured migration logging
- Writes per-record outcomes to a JSONL log file
- Separate from domain logic — consumes MigrationSummary after the fact
"""
import json
from datetime import datetime, UTC
from pathlib import Path

from domain.value_objects.migration_result import MigrationSummary, RecordResult


class MigrationLogger:
    def __init__(self, log_dir: str = "./logs"):
        self._log_dir = Path(log_dir)
        self._log_dir.mkdir(parents=True, exist_ok=True)
        ts = datetime.now(UTC).strftime("%Y%m%d_%H%M%S")
        self._log_path = self._log_dir / f"migration_{ts}.jsonl"

    def write_summary(self, summary: MigrationSummary) -> str:
        with open(self._log_path, "w", encoding="utf-8") as f:
            for batch in summary.batches:
                for result in batch.record_results:
                    f.write(json.dumps(self._result_to_dict(result)) + "\n")

            f.write(json.dumps({
                "type": "summary",
                "total_extracted": summary.total_extracted,
                "total_loaded": summary.total_loaded,
                "total_quarantined": summary.total_quarantined,
                "duration_seconds": summary.duration_seconds,
            }) + "\n")

        return str(self._log_path)

    @staticmethod
    def _result_to_dict(result: RecordResult) -> dict:
        return {
            "type": "record",
            "salesforce_id": result.salesforce_id,
            "object_type": result.object_type,
            "status": result.status.value,
            "nexus_id": result.nexus_id or "",
            "message": result.message,
        }
