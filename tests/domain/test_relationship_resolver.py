"""
Relationship Resolver Tests — Pure Domain Logic
"""
from domain.services.relationship_resolver import RelationshipResolver
from domain.value_objects.migration_result import RecordStatus


class TestRelationshipResolver:
    def test_register_and_resolve(self):
        resolver = RelationshipResolver()
        resolver.register("001SF", "nexus-1")
        assert resolver.resolve("001SF") == "nexus-1"

    def test_resolve_unknown_returns_none_and_warns(self):
        resolver = RelationshipResolver()
        result = resolver.resolve("unknown-id", "Test")
        assert result is None
        assert len(resolver.unresolved_warnings) == 1
        assert resolver.unresolved_warnings[0].status == RecordStatus.WARNING

    def test_resolve_empty_string_returns_none(self):
        resolver = RelationshipResolver()
        assert resolver.resolve("") is None
        assert len(resolver.unresolved_warnings) == 0

    def test_lookup_size(self):
        resolver = RelationshipResolver()
        resolver.register("001", "n1")
        resolver.register("002", "n2")
        assert resolver.lookup_size == 2
