"""
Generate Report Command Tests
"""
from application.commands.generate_report import GenerateReportCommand
from domain.value_objects.migration_result import (
    BatchResult, MigrationSummary, RecordResult, RecordStatus,
)


class TestGenerateReport:
    def test_produces_html(self):
        summary = MigrationSummary(
            batches=(
                BatchResult(
                    object_type="Account", total=10, success_count=9,
                    warning_count=0, error_count=0, quarantined_count=1,
                    record_results=(
                        RecordResult(salesforce_id="001", object_type="Account",
                                    status=RecordStatus.QUARANTINED, message="Missing name"),
                    ),
                ),
            ),
            total_extracted=10, total_loaded=9, total_quarantined=1,
            duration_seconds=5.2,
        )
        html = GenerateReportCommand(summary=summary).execute()
        assert "<!DOCTYPE html>" in html
        assert "Account" in html
        assert "10" in html
        assert "5.2" in html
        assert "Missing name" in html

    def test_empty_migration(self):
        summary = MigrationSummary(batches=(), total_extracted=0, total_loaded=0)
        html = GenerateReportCommand(summary=summary).execute()
        assert "<!DOCTYPE html>" in html
