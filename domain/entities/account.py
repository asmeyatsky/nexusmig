"""
Account Entity (Salesforce) -> Company (Nexus)

Architectural Intent:
- Immutable aggregate representing a Salesforce Account record
- Business rules for validation and transformation are encapsulated here
- Domain events collected for state transitions
"""
from dataclasses import dataclass, field, replace
from datetime import datetime, UTC

from domain.events.event_base import DomainEvent
from domain.value_objects.errors import ValidationError


@dataclass(frozen=True)
class Account:
    sf_id: str
    name: str
    industry: str = ""
    website: str = ""
    phone: str = ""
    billing_street: str = ""
    billing_city: str = ""
    billing_state: str = ""
    billing_postal_code: str = ""
    billing_country: str = ""
    description: str = ""
    annual_revenue: float | None = None
    number_of_employees: int | None = None
    owner_name: str = ""
    created_date: str = ""
    raw_data: dict = field(default_factory=dict)
    domain_events: tuple[DomainEvent, ...] = ()

    def validate(self) -> "Account":
        if not self.name or not self.name.strip():
            raise ValidationError(f"Account {self.sf_id}: Name is required")
        return self

    def to_nexus_company(self) -> dict:
        return {
            "name": self.name.strip(),
            "industry": self.industry,
            "website": self.website,
            "phone": self.phone,
            "address": {
                "street": self.billing_street,
                "city": self.billing_city,
                "state": self.billing_state,
                "postal_code": self.billing_postal_code,
                "country": self.billing_country,
            },
            "description": self.description,
            "annual_revenue": self.annual_revenue,
            "employee_count": self.number_of_employees,
            "owner": self.owner_name,
            "source": "salesforce_migration",
            "external_id": self.sf_id,
        }

    def with_events(self, *events: DomainEvent) -> "Account":
        return replace(self, domain_events=self.domain_events + events)
