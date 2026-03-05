"""
Opportunity Entity (Salesforce) -> Deal (Nexus)

Architectural Intent:
- Immutable aggregate for Salesforce Opportunity records
- Stage mapping is a domain concern (business rule)
- Preserves Account relationship via account_sf_id for two-pass resolution
"""
from dataclasses import dataclass, field, replace

from domain.events.event_base import DomainEvent
from domain.value_objects.errors import ValidationError


DEFAULT_STAGE_MAP: dict[str, str] = {
    "Prospecting": "Discovery",
    "Qualification": "Qualified",
    "Needs Analysis": "Qualified",
    "Value Proposition": "Proposal",
    "Id. Decision Makers": "Proposal",
    "Perception Analysis": "Proposal",
    "Proposal/Price Quote": "Proposal",
    "Negotiation/Review": "Negotiation",
    "Closed Won": "Won",
    "Closed Lost": "Lost",
}


@dataclass(frozen=True)
class Opportunity:
    sf_id: str
    name: str = ""
    stage_name: str = ""
    amount: float | None = None
    close_date: str = ""
    probability: float | None = None
    account_sf_id: str = ""
    contact_sf_id: str = ""
    description: str = ""
    lead_source: str = ""
    opportunity_type: str = ""
    owner_name: str = ""
    created_date: str = ""
    raw_data: dict = field(default_factory=dict)
    domain_events: tuple[DomainEvent, ...] = ()

    def validate(self) -> "Opportunity":
        if not self.name or not self.name.strip():
            raise ValidationError(f"Opportunity {self.sf_id}: Name is required")
        return self

    def map_stage(self, custom_map: dict[str, str] | None = None) -> str:
        stage_map = custom_map if custom_map else DEFAULT_STAGE_MAP
        return stage_map.get(self.stage_name, self.stage_name)

    def to_nexus_deal(
        self,
        account_nexus_id: str | None = None,
        contact_nexus_id: str | None = None,
        stage_map: dict[str, str] | None = None,
    ) -> dict:
        payload: dict = {
            "name": self.name.strip(),
            "stage": self.map_stage(stage_map),
            "amount": self.amount or 0.0,
            "close_date": self.close_date,
            "probability": self.probability,
            "description": self.description,
            "lead_source": self.lead_source,
            "deal_type": self.opportunity_type,
            "owner": self.owner_name,
            "source": "salesforce_migration",
            "external_id": self.sf_id,
        }
        if account_nexus_id:
            payload["company_id"] = account_nexus_id
        if contact_nexus_id:
            payload["contact_id"] = contact_nexus_id
        return payload

    def with_events(self, *events: DomainEvent) -> "Opportunity":
        return replace(self, domain_events=self.domain_events + events)
