"""
Run History Tests
"""
import tempfile
from domain.value_objects.migration_result import MigrationSummary
from infrastructure.logging.run_history import RunHistory


def _sample_summary(**overrides) -> MigrationSummary:
    defaults = dict(
        batches=(), total_extracted=100, total_loaded=95,
        total_quarantined=5, duration_seconds=12.3,
    )
    defaults.update(overrides)
    return MigrationSummary(**defaults)


class TestRunHistory:
    def test_record_and_list(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            history = RunHistory(log_dir=tmpdir)
            history.record(
                summary=_sample_summary(),
                log_path="/tmp/migration_test.jsonl",
                config_hash="abc123",
                input_mode="csv",
                output_mode="file",
            )
            runs = history.list_runs()
            assert len(runs) == 1
            assert runs[0].total_extracted == 100
            assert runs[0].total_loaded == 95
            assert runs[0].config_hash == "abc123"

    def test_multiple_runs_ordered(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            history = RunHistory(log_dir=tmpdir)
            history.record(_sample_summary(total_extracted=10), "/tmp/a.jsonl")
            history.record(_sample_summary(total_extracted=20), "/tmp/b.jsonl")
            history.record(_sample_summary(total_extracted=30), "/tmp/c.jsonl")

            runs = history.list_runs()
            assert len(runs) == 3
            # Most recent first
            assert runs[0].total_extracted == 30

    def test_get_latest(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            history = RunHistory(log_dir=tmpdir)
            history.record(_sample_summary(), "/tmp/a.jsonl", dry_run=True)
            history.record(_sample_summary(), "/tmp/b.jsonl", dry_run=False)

            latest = history.get_latest()
            assert latest is not None
            assert latest.dry_run is False

            latest_dry = history.get_latest(dry_run=True)
            assert latest_dry is not None
            assert latest_dry.dry_run is True

    def test_success_flag(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            history = RunHistory(log_dir=tmpdir)
            history.record(_sample_summary(total_quarantined=0), "/tmp/ok.jsonl")
            history.record(_sample_summary(total_quarantined=5), "/tmp/warn.jsonl")

            runs = history.list_runs()
            assert runs[0].success is False  # 5 quarantined
            assert runs[1].success is True   # 0 quarantined

    def test_empty_history(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            history = RunHistory(log_dir=tmpdir)
            assert history.list_runs() == []
            assert history.get_latest() is None

    def test_limit(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            history = RunHistory(log_dir=tmpdir)
            for i in range(10):
                history.record(_sample_summary(), f"/tmp/{i}.jsonl")
            assert len(history.list_runs(limit=3)) == 3
