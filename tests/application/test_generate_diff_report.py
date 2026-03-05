"""
Diff Report Generation Tests
"""
from application.commands.generate_diff_report import GenerateDiffReportCommand
from domain.services.diff_service import DiffService, MigrationDiff, BatchDiff
from domain.value_objects.migration_result import BatchResult, MigrationSummary


class TestGenerateDiffReport:
    def test_produces_html_with_regression(self):
        diff = MigrationDiff(
            baseline_label="dry-run",
            current_label="live",
            batch_diffs=(BatchDiff(
                object_type="Account",
                baseline_total=10, current_total=10,
                baseline_success=10, current_success=8,
                baseline_quarantined=0, current_quarantined=2,
                new_errors=0, resolved_errors=0,
            ),),
            extracted_delta=0, loaded_delta=-2,
            quarantined_delta=2, duration_delta=1.5,
            is_regression=True,
        )
        html = GenerateDiffReportCommand(diff=diff).execute()
        assert "<!DOCTYPE html>" in html
        assert "REGRESSION" in html
        assert "dry-run" in html
        assert "live" in html
        assert "Account" in html

    def test_no_regression_verdict(self):
        diff = MigrationDiff(
            baseline_label="run-1",
            current_label="run-2",
            batch_diffs=(),
            extracted_delta=0, loaded_delta=0,
            quarantined_delta=0, duration_delta=0.0,
            is_regression=False,
        )
        html = GenerateDiffReportCommand(diff=diff).execute()
        assert "safe to proceed" in html.lower()

    def test_full_round_trip(self):
        baseline = MigrationSummary(
            batches=(BatchResult(
                object_type="Account", total=10, success_count=9,
                warning_count=0, error_count=1, quarantined_count=0,
            ),),
            total_extracted=10, total_loaded=9, duration_seconds=5.0,
        )
        current = MigrationSummary(
            batches=(BatchResult(
                object_type="Account", total=10, success_count=10,
                warning_count=0, error_count=0, quarantined_count=0,
            ),),
            total_extracted=10, total_loaded=10, duration_seconds=4.0,
        )
        diff = DiffService().compare(baseline, current)
        html = GenerateDiffReportCommand(diff=diff).execute()
        assert "<!DOCTYPE html>" in html
        assert not diff.is_regression
