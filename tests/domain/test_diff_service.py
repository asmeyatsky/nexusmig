"""
Diff Service Tests -- Pure Domain Logic
"""
from domain.services.diff_service import DiffService
from domain.value_objects.migration_result import BatchResult, MigrationSummary


def _make_summary(accounts_total=10, accounts_success=10, accounts_quarantined=0,
                   accounts_errors=0, duration=5.0) -> MigrationSummary:
    return MigrationSummary(
        batches=(BatchResult(
            object_type="Account", total=accounts_total,
            success_count=accounts_success, warning_count=0,
            error_count=accounts_errors, quarantined_count=accounts_quarantined,
        ),),
        total_extracted=accounts_total,
        total_loaded=accounts_success,
        total_quarantined=accounts_quarantined,
        duration_seconds=duration,
    )


class TestDiffService:
    def setup_method(self):
        self.service = DiffService()

    def test_identical_runs_no_regression(self):
        a = _make_summary()
        b = _make_summary()
        diff = self.service.compare(a, b)
        assert not diff.is_regression
        assert diff.extracted_delta == 0
        assert diff.loaded_delta == 0
        assert diff.quarantined_delta == 0

    def test_new_errors_is_regression(self):
        baseline = _make_summary(accounts_errors=0)
        current = _make_summary(accounts_errors=3, accounts_success=7)
        diff = self.service.compare(baseline, current)
        assert diff.is_regression
        assert diff.batch_diffs[0].new_errors == 3

    def test_increased_quarantine_is_regression(self):
        baseline = _make_summary(accounts_quarantined=1, accounts_success=9)
        current = _make_summary(accounts_quarantined=3, accounts_success=7)
        diff = self.service.compare(baseline, current)
        assert diff.is_regression
        assert diff.quarantined_delta == 2

    def test_resolved_errors_not_regression(self):
        baseline = _make_summary(accounts_errors=5, accounts_success=5)
        current = _make_summary(accounts_errors=0, accounts_success=10)
        diff = self.service.compare(baseline, current)
        assert not diff.is_regression
        assert diff.batch_diffs[0].resolved_errors == 5

    def test_duration_delta(self):
        baseline = _make_summary(duration=10.0)
        current = _make_summary(duration=7.0)
        diff = self.service.compare(baseline, current)
        assert diff.duration_delta == -3.0

    def test_labels_preserved(self):
        diff = self.service.compare(
            _make_summary(), _make_summary(),
            baseline_label="dry-run-1", current_label="live-1",
        )
        assert diff.baseline_label == "dry-run-1"
        assert diff.current_label == "live-1"

    def test_missing_object_type_in_one_run(self):
        baseline = MigrationSummary(
            batches=(
                BatchResult(object_type="Account", total=10, success_count=10,
                           warning_count=0, error_count=0, quarantined_count=0),
            ),
            total_extracted=10, total_loaded=10,
        )
        current = MigrationSummary(
            batches=(
                BatchResult(object_type="Account", total=10, success_count=10,
                           warning_count=0, error_count=0, quarantined_count=0),
                BatchResult(object_type="Contact", total=5, success_count=5,
                           warning_count=0, error_count=0, quarantined_count=0),
            ),
            total_extracted=15, total_loaded=15,
        )
        diff = self.service.compare(baseline, current)
        assert len(diff.batch_diffs) == 2
        contact_diff = next(d for d in diff.batch_diffs if d.object_type == "Contact")
        assert contact_diff.baseline_total == 0
        assert contact_diff.current_total == 5
