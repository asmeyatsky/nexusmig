"""
Loader Ports

Architectural Intent:
- Defines interfaces for loading transformed data into Nexus CRM
- Supports API push and file export — same port, different adapters
- Returns per-record results for auditability
"""
from typing import Protocol

from domain.value_objects.migration_result import RecordResult


class NexusLoaderPort(Protocol):
    async def load_companies(self, records: list[dict]) -> list[RecordResult]: ...
    async def load_contacts(self, records: list[dict]) -> list[RecordResult]: ...
    async def load_deals(self, records: list[dict]) -> list[RecordResult]: ...
    async def load_activities(self, records: list[dict]) -> list[RecordResult]: ...


class FileExporterPort(Protocol):
    async def export(self, object_type: str, records: list[dict], fmt: str) -> str: ...
