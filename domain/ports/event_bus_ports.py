"""
Event Bus Port

Architectural Intent:
- Defines the interface for publishing domain events
- Application layer dispatches events collected from aggregates
"""
from typing import Protocol, Callable

from domain.events.event_base import DomainEvent


class EventBusPort(Protocol):
    async def publish(self, events: list[DomainEvent]) -> None: ...
    async def subscribe(self, event_type: type, handler: Callable) -> None: ...
