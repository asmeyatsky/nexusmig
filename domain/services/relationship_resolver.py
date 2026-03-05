"""
Relationship Resolver Domain Service

Architectural Intent:
- Maintains an in-memory SF ID -> Nexus ID lookup table
- Used in the two-pass migration strategy:
  Pass 1: Accounts & Contacts migrated, lookup table populated
  Pass 2: Opportunities & Activities resolve references via this service
- Pure domain logic — no infrastructure dependencies
"""
from domain.value_objects.migration_result import RecordResult, RecordStatus


class RelationshipResolver:
    def __init__(self) -> None:
        self._lookup: dict[str, str] = {}
        self._unresolved: list[RecordResult] = []

    def register(self, salesforce_id: str, nexus_id: str) -> None:
        if salesforce_id:
            self._lookup[salesforce_id] = nexus_id

    def resolve(self, salesforce_id: str, context: str = "") -> str | None:
        if not salesforce_id:
            return None
        nexus_id = self._lookup.get(salesforce_id)
        if nexus_id is None:
            self._unresolved.append(RecordResult(
                salesforce_id=salesforce_id,
                object_type=context,
                status=RecordStatus.WARNING,
                message=f"Unresolved reference: {salesforce_id} not found in lookup",
            ))
        return nexus_id

    @property
    def unresolved_warnings(self) -> list[RecordResult]:
        return list(self._unresolved)

    @property
    def lookup_size(self) -> int:
        return len(self._lookup)
