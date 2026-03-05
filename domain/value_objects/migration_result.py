"""
Migration Result Value Objects

Architectural Intent:
- Immutable result records for per-record and per-batch outcomes
- Used across all layers to communicate migration status
- No identity — pure value semantics
"""
from dataclasses import dataclass, field
from enum import Enum


class RecordStatus(Enum):
    SUCCESS = "success"
    WARNING = "warning"
    ERROR = "error"
    QUARANTINED = "quarantined"


@dataclass(frozen=True)
class RecordResult:
    salesforce_id: str
    object_type: str
    status: RecordStatus
    nexus_id: str | None = None
    message: str = ""


@dataclass(frozen=True)
class BatchResult:
    object_type: str
    total: int
    success_count: int
    warning_count: int
    error_count: int
    quarantined_count: int
    record_results: tuple[RecordResult, ...] = ()


@dataclass(frozen=True)
class MigrationSummary:
    batches: tuple[BatchResult, ...]
    total_extracted: int = 0
    total_loaded: int = 0
    total_quarantined: int = 0
    duration_seconds: float = 0.0
    warnings: tuple[str, ...] = ()
