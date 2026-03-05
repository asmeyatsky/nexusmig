"""
Run History Index

Architectural Intent:
- Infrastructure concern: maintains a lightweight JSON index of past migration runs
- Each entry records timestamp, config hash, outcome summary, and log file path
- Enables run-to-run comparison and trend tracking
"""
import hashlib
import json
from datetime import datetime, UTC
from pathlib import Path

from domain.value_objects.migration_result import MigrationSummary


_INDEX_FILENAME = "run_history.json"


class RunHistoryEntry:
    def __init__(self, data: dict):
        self.run_id: str = data["run_id"]
        self.timestamp: str = data["timestamp"]
        self.log_path: str = data["log_path"]
        self.config_hash: str = data.get("config_hash", "")
        self.input_mode: str = data.get("input_mode", "")
        self.output_mode: str = data.get("output_mode", "")
        self.total_extracted: int = data.get("total_extracted", 0)
        self.total_loaded: int = data.get("total_loaded", 0)
        self.total_quarantined: int = data.get("total_quarantined", 0)
        self.duration_seconds: float = data.get("duration_seconds", 0.0)
        self.success: bool = data.get("success", False)
        self.dry_run: bool = data.get("dry_run", False)

    def to_dict(self) -> dict:
        return {
            "run_id": self.run_id,
            "timestamp": self.timestamp,
            "log_path": self.log_path,
            "config_hash": self.config_hash,
            "input_mode": self.input_mode,
            "output_mode": self.output_mode,
            "total_extracted": self.total_extracted,
            "total_loaded": self.total_loaded,
            "total_quarantined": self.total_quarantined,
            "duration_seconds": self.duration_seconds,
            "success": self.success,
            "dry_run": self.dry_run,
        }


class RunHistory:
    def __init__(self, log_dir: str = "./logs"):
        self._log_dir = Path(log_dir)
        self._log_dir.mkdir(parents=True, exist_ok=True)
        self._index_path = self._log_dir / _INDEX_FILENAME

    def record(
        self,
        summary: MigrationSummary,
        log_path: str,
        config_hash: str = "",
        input_mode: str = "",
        output_mode: str = "",
        dry_run: bool = False,
    ) -> RunHistoryEntry:
        entries = self._load_entries()
        ts = datetime.now(UTC)
        run_id = f"run_{ts.strftime('%Y%m%d_%H%M%S')}_{len(entries) + 1}"

        entry = RunHistoryEntry({
            "run_id": run_id,
            "timestamp": ts.isoformat(),
            "log_path": log_path,
            "config_hash": config_hash,
            "input_mode": input_mode,
            "output_mode": output_mode,
            "total_extracted": summary.total_extracted,
            "total_loaded": summary.total_loaded,
            "total_quarantined": summary.total_quarantined,
            "duration_seconds": summary.duration_seconds,
            "success": summary.total_quarantined == 0,
            "dry_run": dry_run,
        })

        entries.insert(0, entry)
        self._save_entries(entries)
        return entry

    def list_runs(self, limit: int = 20) -> list[RunHistoryEntry]:
        return self._load_entries()[:limit]

    def get_run(self, run_id: str) -> RunHistoryEntry | None:
        for entry in self._load_entries():
            if entry.run_id == run_id:
                return entry
        return None

    def get_latest(self, dry_run: bool | None = None) -> RunHistoryEntry | None:
        for entry in self._load_entries():
            if dry_run is None or entry.dry_run == dry_run:
                return entry
        return None

    def _load_entries(self) -> list[RunHistoryEntry]:
        if not self._index_path.exists():
            return []
        with open(self._index_path, "r") as f:
            data = json.load(f)
        return [RunHistoryEntry(d) for d in data]

    def _save_entries(self, entries: list[RunHistoryEntry]) -> None:
        with open(self._index_path, "w") as f:
            json.dump([e.to_dict() for e in entries], f, indent=2)

    @staticmethod
    def hash_config(config_path: str) -> str:
        content = Path(config_path).read_bytes()
        return hashlib.sha256(content).hexdigest()[:12]
