"""
Migration Domain Events

Events emitted during the migration lifecycle.
"""
from dataclasses import dataclass
from domain.events.event_base import DomainEvent


@dataclass(frozen=True)
class ExtractionStartedEvent(DomainEvent):
    object_type: str = ""
    source_mode: str = ""


@dataclass(frozen=True)
class ExtractionCompletedEvent(DomainEvent):
    object_type: str = ""
    record_count: int = 0


@dataclass(frozen=True)
class TransformCompletedEvent(DomainEvent):
    object_type: str = ""
    success_count: int = 0
    quarantined_count: int = 0


@dataclass(frozen=True)
class LoadCompletedEvent(DomainEvent):
    object_type: str = ""
    loaded_count: int = 0
    failed_count: int = 0


@dataclass(frozen=True)
class MigrationCompletedEvent(DomainEvent):
    total_extracted: int = 0
    total_loaded: int = 0
    total_quarantined: int = 0
