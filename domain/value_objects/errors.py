"""Domain-level error types."""


class DomainError(Exception):
    pass


class ValidationError(DomainError):
    pass


class MappingError(DomainError):
    pass
