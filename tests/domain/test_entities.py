"""
Domain Entity Tests — Pure Unit Tests, No Mocks

Tests immutability, validation, and Nexus mapping for all four entity types.
"""
import pytest
from domain.entities.account import Account
from domain.entities.contact import Contact
from domain.entities.opportunity import Opportunity
from domain.entities.activity import Activity
from domain.value_objects.errors import ValidationError


class TestAccount:
    def test_valid_account_maps_to_nexus(self):
        account = Account(sf_id="001ABC", name="Acme Corp", industry="Tech", website="acme.com")
        nexus = account.to_nexus_company()
        assert nexus["name"] == "Acme Corp"
        assert nexus["industry"] == "Tech"
        assert nexus["external_id"] == "001ABC"
        assert nexus["source"] == "salesforce_migration"

    def test_validate_raises_on_empty_name(self):
        account = Account(sf_id="001ABC", name="")
        with pytest.raises(ValidationError, match="Name is required"):
            account.validate()

    def test_validate_raises_on_whitespace_name(self):
        account = Account(sf_id="001ABC", name="   ")
        with pytest.raises(ValidationError):
            account.validate()

    def test_immutability(self):
        account = Account(sf_id="001ABC", name="Test")
        with pytest.raises(AttributeError):
            account.name = "Changed"

    def test_with_events_returns_new_instance(self):
        from domain.events.event_base import DomainEvent
        account = Account(sf_id="001ABC", name="Test")
        event = DomainEvent(aggregate_id="001ABC")
        updated = account.with_events(event)
        assert len(updated.domain_events) == 1
        assert len(account.domain_events) == 0
        assert updated is not account

    def test_address_mapping(self):
        account = Account(
            sf_id="001ABC", name="Test",
            billing_street="123 Main St", billing_city="Springfield",
            billing_state="IL", billing_postal_code="62704", billing_country="US",
        )
        nexus = account.to_nexus_company()
        assert nexus["address"]["street"] == "123 Main St"
        assert nexus["address"]["city"] == "Springfield"


class TestContact:
    def test_valid_contact_maps_to_nexus(self):
        contact = Contact(sf_id="003ABC", first_name="John", last_name="Doe", email="John@Test.com")
        nexus = contact.to_nexus_contact()
        assert nexus["first_name"] == "John"
        assert nexus["last_name"] == "Doe"
        assert nexus["email"] == "john@test.com"

    def test_validate_raises_on_empty_last_name(self):
        contact = Contact(sf_id="003ABC", last_name="")
        with pytest.raises(ValidationError, match="LastName is required"):
            contact.validate()

    def test_contact_with_company_id(self):
        contact = Contact(sf_id="003ABC", last_name="Doe")
        nexus = contact.to_nexus_contact(account_nexus_id="nexus-123")
        assert nexus["company_id"] == "nexus-123"

    def test_contact_without_company_id(self):
        contact = Contact(sf_id="003ABC", last_name="Doe")
        nexus = contact.to_nexus_contact()
        assert "company_id" not in nexus


class TestOpportunity:
    def test_default_stage_mapping(self):
        opp = Opportunity(sf_id="006ABC", name="Big Deal", stage_name="Prospecting")
        assert opp.map_stage() == "Discovery"

    def test_closed_won_maps_to_won(self):
        opp = Opportunity(sf_id="006ABC", name="Deal", stage_name="Closed Won")
        assert opp.map_stage() == "Won"

    def test_custom_stage_mapping(self):
        opp = Opportunity(sf_id="006ABC", name="Deal", stage_name="Custom Stage")
        assert opp.map_stage({"Custom Stage": "Custom Nexus"}) == "Custom Nexus"

    def test_unknown_stage_passes_through(self):
        opp = Opportunity(sf_id="006ABC", name="Deal", stage_name="Unknown")
        assert opp.map_stage() == "Unknown"

    def test_validate_raises_on_empty_name(self):
        opp = Opportunity(sf_id="006ABC", name="")
        with pytest.raises(ValidationError):
            opp.validate()

    def test_nexus_deal_mapping(self):
        opp = Opportunity(sf_id="006ABC", name="Big Deal", amount=50000.0,
                         stage_name="Negotiation/Review")
        nexus = opp.to_nexus_deal(account_nexus_id="comp-1", contact_nexus_id="cont-1")
        assert nexus["stage"] == "Negotiation"
        assert nexus["amount"] == 50000.0
        assert nexus["company_id"] == "comp-1"
        assert nexus["contact_id"] == "cont-1"


class TestActivity:
    def test_task_maps_to_nexus(self):
        activity = Activity(sf_id="00T123", subject="Follow up call",
                           activity_type="task", status="Not Started", priority="High")
        nexus = activity.to_nexus_activity()
        assert nexus["subject"] == "Follow up call"
        assert nexus["type"] == "task"
        assert nexus["status"] == "pending"
        assert nexus["priority"] == "high"

    def test_completed_status_mapping(self):
        activity = Activity(sf_id="00T123", subject="Done", status="Completed")
        nexus = activity.to_nexus_activity()
        assert nexus["status"] == "completed"

    def test_validate_raises_on_empty_subject(self):
        activity = Activity(sf_id="00T123", subject="")
        with pytest.raises(ValidationError, match="Subject is required"):
            activity.validate()

    def test_related_ids_in_nexus_mapping(self):
        activity = Activity(sf_id="00T123", subject="Call")
        nexus = activity.to_nexus_activity(related_entity_id="deal-1", contact_nexus_id="cont-1")
        assert nexus["related_to_id"] == "deal-1"
        assert nexus["contact_id"] == "cont-1"
