"""
Mapping Service Tests — Pure Domain Logic
"""
from domain.services.mapping_service import MappingService


class TestMappingService:
    def setup_method(self):
        self.service = MappingService()

    def test_map_account_basic(self):
        raw = {"Id": "001ABC", "Name": "Acme", "Industry": "Tech", "Website": "acme.com"}
        account = self.service.map_account(raw)
        assert account.sf_id == "001ABC"
        assert account.name == "Acme"
        assert account.industry == "Tech"

    def test_map_contact_basic(self):
        raw = {"Id": "003ABC", "FirstName": "Jane", "LastName": "Doe", "Email": "jane@test.com",
               "AccountId": "001ABC"}
        contact = self.service.map_contact(raw)
        assert contact.sf_id == "003ABC"
        assert contact.last_name == "Doe"
        assert contact.account_sf_id == "001ABC"

    def test_map_opportunity_basic(self):
        raw = {"Id": "006ABC", "Name": "Deal", "StageName": "Prospecting", "Amount": "50000"}
        opp = self.service.map_opportunity(raw)
        assert opp.sf_id == "006ABC"
        assert opp.amount == 50000.0

    def test_map_task(self):
        raw = {"Id": "00T123", "Subject": "Call", "Status": "Not Started",
               "Priority": "High", "WhoId": "003ABC", "WhatId": "001ABC"}
        activity = self.service.map_task(raw)
        assert activity.activity_type == "task"
        assert activity.who_id == "003ABC"

    def test_map_event(self):
        raw = {"Id": "00U123", "Subject": "Meeting", "StartDateTime": "2024-01-15T10:00:00",
               "EndDateTime": "2024-01-15T11:00:00"}
        activity = self.service.map_event(raw)
        assert activity.activity_type == "event"

    def test_field_overrides(self):
        service = MappingService(field_overrides={
            "Account": {"Company_Name__c": "Name"}
        })
        raw = {"Id": "001ABC", "Company_Name__c": "Custom Corp"}
        account = service.map_account(raw)
        assert account.name == "Custom Corp"

    def test_owner_extraction_from_dict(self):
        raw = {"Id": "001ABC", "Name": "Test", "Owner": {"Name": "Admin User"}}
        account = self.service.map_account(raw)
        assert account.owner_name == "Admin User"

    def test_safe_float_handles_none(self):
        raw = {"Id": "006ABC", "Name": "Deal", "Amount": None}
        opp = self.service.map_opportunity(raw)
        assert opp.amount is None

    def test_safe_float_handles_invalid(self):
        raw = {"Id": "006ABC", "Name": "Deal", "Amount": "not-a-number"}
        opp = self.service.map_opportunity(raw)
        assert opp.amount is None

    def test_missing_fields_default_to_empty(self):
        raw = {"Id": "001ABC"}
        account = self.service.map_account(raw)
        assert account.name == ""
        assert account.industry == ""
