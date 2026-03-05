"""
Migration Status Query

Returns the current state of a migration run (for MCP resource exposure).
"""
from dataclasses import dataclass

from domain.value_objects.migration_result import MigrationSummary


@dataclass
class MigrationStatusQuery:
    summary: MigrationSummary | None = None

    def execute(self) -> dict:
        if not self.summary:
            return {"status": "no_migration_run"}
        return {
            "status": "completed",
            "total_extracted": self.summary.total_extracted,
            "total_loaded": self.summary.total_loaded,
            "total_quarantined": self.summary.total_quarantined,
            "duration_seconds": self.summary.duration_seconds,
            "batches": [
                {
                    "object_type": b.object_type,
                    "total": b.total,
                    "success": b.success_count,
                    "warnings": b.warning_count,
                    "errors": b.error_count,
                    "quarantined": b.quarantined_count,
                }
                for b in self.summary.batches
            ],
        }
