"""
Salesforce ID Value Object

Encapsulates the 15/18-character Salesforce record ID with validation.
"""
from dataclasses import dataclass

from domain.value_objects.errors import DomainError


@dataclass(frozen=True)
class SalesforceId:
    value: str

    def __post_init__(self):
        if not self.value or len(self.value) not in (15, 18):
            raise DomainError(
                f"Invalid Salesforce ID '{self.value}': must be 15 or 18 characters"
            )
