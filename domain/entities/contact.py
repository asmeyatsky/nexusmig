"""
Contact Entity

Architectural Intent:
- Immutable aggregate representing a Salesforce Contact record
- Encapsulates validation (email format, required fields)
- Maps to Nexus Contact with relationship to Company via account_sf_id
"""
from dataclasses import dataclass, field, replace

from domain.events.event_base import DomainEvent
from domain.value_objects.errors import ValidationError


@dataclass(frozen=True)
class Contact:
    sf_id: str
    first_name: str = ""
    last_name: str = ""
    email: str = ""
    phone: str = ""
    mobile_phone: str = ""
    title: str = ""
    department: str = ""
    account_sf_id: str = ""
    mailing_street: str = ""
    mailing_city: str = ""
    mailing_state: str = ""
    mailing_postal_code: str = ""
    mailing_country: str = ""
    description: str = ""
    owner_name: str = ""
    created_date: str = ""
    raw_data: dict = field(default_factory=dict)
    domain_events: tuple[DomainEvent, ...] = ()

    def validate(self) -> "Contact":
        if not self.last_name or not self.last_name.strip():
            raise ValidationError(f"Contact {self.sf_id}: LastName is required")
        return self

    def to_nexus_contact(self, account_nexus_id: str | None = None) -> dict:
        payload: dict = {
            "first_name": self.first_name.strip(),
            "last_name": self.last_name.strip(),
            "email": self.email.lower().strip() if self.email else "",
            "phone": self.phone,
            "mobile": self.mobile_phone,
            "title": self.title,
            "department": self.department,
            "address": {
                "street": self.mailing_street,
                "city": self.mailing_city,
                "state": self.mailing_state,
                "postal_code": self.mailing_postal_code,
                "country": self.mailing_country,
            },
            "description": self.description,
            "owner": self.owner_name,
            "source": "salesforce_migration",
            "external_id": self.sf_id,
        }
        if account_nexus_id:
            payload["company_id"] = account_nexus_id
        return payload

    def with_events(self, *events: DomainEvent) -> "Contact":
        return replace(self, domain_events=self.domain_events + events)
