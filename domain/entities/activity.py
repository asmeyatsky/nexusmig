"""
Activity Entity (Salesforce Tasks & Events) -> Nexus Activity

Architectural Intent:
- Immutable aggregate for Salesforce Task and Event records
- Normalises both SF object types into a unified Nexus Activity model
- Preserves WhatId/WhoId references for two-pass relationship resolution
"""
from dataclasses import dataclass, field, replace

from domain.events.event_base import DomainEvent
from domain.value_objects.errors import ValidationError


@dataclass(frozen=True)
class Activity:
    sf_id: str
    subject: str = ""
    activity_type: str = ""  # "task" or "event"
    status: str = ""
    priority: str = ""
    description: str = ""
    activity_date: str = ""
    due_date: str = ""
    who_id: str = ""  # Contact/Lead SF ID
    what_id: str = ""  # Account/Opportunity SF ID
    owner_name: str = ""
    is_completed: bool = False
    created_date: str = ""
    raw_data: dict = field(default_factory=dict)
    domain_events: tuple[DomainEvent, ...] = ()

    def validate(self) -> "Activity":
        if not self.subject or not self.subject.strip():
            raise ValidationError(f"Activity {self.sf_id}: Subject is required")
        return self

    def to_nexus_activity(
        self,
        related_entity_id: str | None = None,
        contact_nexus_id: str | None = None,
    ) -> dict:
        payload: dict = {
            "subject": self.subject.strip(),
            "type": self.activity_type,
            "status": self._map_status(),
            "priority": self.priority.lower() if self.priority else "normal",
            "description": self.description,
            "due_date": self.due_date or self.activity_date,
            "completed": self.is_completed,
            "owner": self.owner_name,
            "source": "salesforce_migration",
            "external_id": self.sf_id,
        }
        if related_entity_id:
            payload["related_to_id"] = related_entity_id
        if contact_nexus_id:
            payload["contact_id"] = contact_nexus_id
        return payload

    def _map_status(self) -> str:
        status_map = {
            "Not Started": "pending",
            "In Progress": "in_progress",
            "Completed": "completed",
            "Waiting on someone else": "waiting",
            "Deferred": "deferred",
        }
        return status_map.get(self.status, self.status.lower() if self.status else "pending")

    def with_events(self, *events: DomainEvent) -> "Activity":
        return replace(self, domain_events=self.domain_events + events)
