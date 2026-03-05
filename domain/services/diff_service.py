"""
Migration Diff Service

Architectural Intent:
- Pure domain logic comparing two MigrationSummary instances
- Primary use case: dry-run vs live-run comparison
- Can also compare any two runs for regression detection
- No infrastructure dependencies
"""
from dataclasses import dataclass

from domain.value_objects.migration_result import MigrationSummary


@dataclass(frozen=True)
class BatchDiff:
    object_type: str
    baseline_total: int
    current_total: int
    baseline_success: int
    current_success: int
    baseline_quarantined: int
    current_quarantined: int
    new_errors: int
    resolved_errors: int


@dataclass(frozen=True)
class MigrationDiff:
    baseline_label: str
    current_label: str
    batch_diffs: tuple[BatchDiff, ...]
    extracted_delta: int
    loaded_delta: int
    quarantined_delta: int
    duration_delta: float
    is_regression: bool


class DiffService:
    def compare(
        self,
        baseline: MigrationSummary,
        current: MigrationSummary,
        baseline_label: str = "dry-run",
        current_label: str = "live",
    ) -> MigrationDiff:
        baseline_batches = {b.object_type: b for b in baseline.batches}
        current_batches = {b.object_type: b for b in current.batches}

        all_types = sorted(set(baseline_batches) | set(current_batches))
        batch_diffs: list[BatchDiff] = []
        total_new_errors = 0

        for obj_type in all_types:
            b = baseline_batches.get(obj_type)
            c = current_batches.get(obj_type)

            b_total = b.total if b else 0
            c_total = c.total if c else 0
            b_success = b.success_count if b else 0
            c_success = c.success_count if c else 0
            b_quarantined = b.quarantined_count if b else 0
            c_quarantined = c.quarantined_count if c else 0
            b_errors = b.error_count if b else 0
            c_errors = c.error_count if c else 0

            new_errors = max(0, c_errors - b_errors)
            resolved_errors = max(0, b_errors - c_errors)
            total_new_errors += new_errors

            batch_diffs.append(BatchDiff(
                object_type=obj_type,
                baseline_total=b_total,
                current_total=c_total,
                baseline_success=b_success,
                current_success=c_success,
                baseline_quarantined=b_quarantined,
                current_quarantined=c_quarantined,
                new_errors=new_errors,
                resolved_errors=resolved_errors,
            ))

        quarantined_delta = current.total_quarantined - baseline.total_quarantined
        is_regression = total_new_errors > 0 or quarantined_delta > 0

        return MigrationDiff(
            baseline_label=baseline_label,
            current_label=current_label,
            batch_diffs=tuple(batch_diffs),
            extracted_delta=current.total_extracted - baseline.total_extracted,
            loaded_delta=current.total_loaded - baseline.total_loaded,
            quarantined_delta=quarantined_delta,
            duration_delta=current.duration_seconds - baseline.duration_seconds,
            is_regression=is_regression,
        )
