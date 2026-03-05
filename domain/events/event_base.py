"""
Domain Event Base

Architectural Intent:
- Immutable event records for cross-boundary communication
- All domain state transitions produce events
- Events are collected on aggregates and dispatched by the application layer
"""
from dataclasses import dataclass, field
from datetime import datetime, UTC


@dataclass(frozen=True)
class DomainEvent:
    aggregate_id: str
    occurred_at: datetime = field(default_factory=lambda: datetime.now(UTC))
