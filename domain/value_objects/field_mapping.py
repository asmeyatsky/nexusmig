"""
Field Mapping Value Objects

Architectural Intent:
- Immutable mapping definitions between Salesforce and Nexus field names
- Encapsulates transformation rules (type coercion, default values)
- Value objects — equality is structural, no identity
"""
from dataclasses import dataclass


@dataclass(frozen=True)
class FieldMapping:
    salesforce_field: str
    nexus_field: str
    required: bool = False
    default: str | None = None
    transform: str | None = None  # Named transform: "lowercase", "iso_date", "url_prefix", etc.


@dataclass(frozen=True)
class StageMapping:
    salesforce_stage: str
    nexus_stage: str


@dataclass(frozen=True)
class ObjectMappingSpec:
    salesforce_object: str
    nexus_object: str
    field_mappings: tuple[FieldMapping, ...]
    stage_mappings: tuple[StageMapping, ...] = ()
