"""
Export Quarantine Command

Exports quarantined records with reasons to a dedicated CSV/JSON file
for easy review and remediation.
"""
import csv
import json
from dataclasses import dataclass
from pathlib import Path

from domain.value_objects.migration_result import MigrationSummary, RecordStatus


@dataclass
class ExportQuarantineCommand:
    summary: MigrationSummary
    output_dir: str
    fmt: str = "csv"

    def execute(self) -> str:
        quarantined = []
        for batch in self.summary.batches:
            for r in batch.record_results:
                if r.status == RecordStatus.QUARANTINED:
                    quarantined.append({
                        "salesforce_id": r.salesforce_id,
                        "object_type": r.object_type,
                        "reason": r.message,
                    })

        output_path = Path(self.output_dir)
        output_path.mkdir(parents=True, exist_ok=True)

        if self.fmt == "json":
            return self._export_json(output_path, quarantined)
        return self._export_csv(output_path, quarantined)

    def _export_csv(self, output_path: Path, records: list[dict]) -> str:
        path = output_path / "quarantined_records.csv"
        with open(path, "w", encoding="utf-8", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=["salesforce_id", "object_type", "reason"])
            writer.writeheader()
            writer.writerows(records)
        return str(path)

    def _export_json(self, output_path: Path, records: list[dict]) -> str:
        path = output_path / "quarantined_records.json"
        with open(path, "w", encoding="utf-8") as f:
            json.dump(records, f, indent=2)
        return str(path)
