"""
Extractor Ports

Architectural Intent:
- Defines the interface for data extraction from Salesforce (API or CSV)
- Lives in the domain layer — no infrastructure dependencies
- Infrastructure adapters implement these protocols
"""
from typing import Protocol


class AccountExtractorPort(Protocol):
    async def extract_accounts(self) -> list[dict]: ...


class ContactExtractorPort(Protocol):
    async def extract_contacts(self) -> list[dict]: ...


class OpportunityExtractorPort(Protocol):
    async def extract_opportunities(self) -> list[dict]: ...


class TaskExtractorPort(Protocol):
    async def extract_tasks(self) -> list[dict]: ...


class EventExtractorPort(Protocol):
    async def extract_events(self) -> list[dict]: ...


class SalesforceExtractorPort(
    AccountExtractorPort,
    ContactExtractorPort,
    OpportunityExtractorPort,
    TaskExtractorPort,
    EventExtractorPort,
    Protocol,
):
    """Composite port for full Salesforce extraction."""
    ...
