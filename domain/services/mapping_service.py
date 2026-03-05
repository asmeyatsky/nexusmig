"""
Mapping Domain Service

Architectural Intent:
- Converts raw Salesforce record dicts into typed domain entities
- Applies field mapping specs including custom overrides
- Pure domain logic — no infrastructure dependencies
"""
from domain.entities.account import Account
from domain.entities.contact import Contact
from domain.entities.opportunity import Opportunity
from domain.entities.activity import Activity


class MappingService:
    def __init__(self, field_overrides: dict[str, dict[str, str]] | None = None):
        self._overrides = field_overrides or {}

    def map_account(self, raw: dict) -> Account:
        r = self._apply_overrides("Account", raw)
        return Account(
            sf_id=r.get("Id", ""),
            name=r.get("Name", ""),
            industry=r.get("Industry", ""),
            website=r.get("Website", ""),
            phone=r.get("Phone", ""),
            billing_street=r.get("BillingStreet", ""),
            billing_city=r.get("BillingCity", ""),
            billing_state=r.get("BillingState", ""),
            billing_postal_code=r.get("BillingPostalCode", ""),
            billing_country=r.get("BillingCountry", ""),
            description=r.get("Description", ""),
            annual_revenue=self._safe_float(r.get("AnnualRevenue")),
            number_of_employees=self._safe_int(r.get("NumberOfEmployees")),
            owner_name=self._extract_owner(r),
            created_date=r.get("CreatedDate", ""),
            raw_data=raw,
        )

    def map_contact(self, raw: dict) -> Contact:
        r = self._apply_overrides("Contact", raw)
        return Contact(
            sf_id=r.get("Id", ""),
            first_name=r.get("FirstName", ""),
            last_name=r.get("LastName", ""),
            email=r.get("Email", ""),
            phone=r.get("Phone", ""),
            mobile_phone=r.get("MobilePhone", ""),
            title=r.get("Title", ""),
            department=r.get("Department", ""),
            account_sf_id=r.get("AccountId", ""),
            mailing_street=r.get("MailingStreet", ""),
            mailing_city=r.get("MailingCity", ""),
            mailing_state=r.get("MailingState", ""),
            mailing_postal_code=r.get("MailingPostalCode", ""),
            mailing_country=r.get("MailingCountry", ""),
            description=r.get("Description", ""),
            owner_name=self._extract_owner(r),
            created_date=r.get("CreatedDate", ""),
            raw_data=raw,
        )

    def map_opportunity(self, raw: dict) -> Opportunity:
        r = self._apply_overrides("Opportunity", raw)
        return Opportunity(
            sf_id=r.get("Id", ""),
            name=r.get("Name", ""),
            stage_name=r.get("StageName", ""),
            amount=self._safe_float(r.get("Amount")),
            close_date=r.get("CloseDate", ""),
            probability=self._safe_float(r.get("Probability")),
            account_sf_id=r.get("AccountId", ""),
            contact_sf_id=r.get("ContactId", ""),
            description=r.get("Description", ""),
            lead_source=r.get("LeadSource", ""),
            opportunity_type=r.get("Type", ""),
            owner_name=self._extract_owner(r),
            created_date=r.get("CreatedDate", ""),
            raw_data=raw,
        )

    def map_task(self, raw: dict) -> Activity:
        r = self._apply_overrides("Task", raw)
        return Activity(
            sf_id=r.get("Id", ""),
            subject=r.get("Subject", ""),
            activity_type="task",
            status=r.get("Status", ""),
            priority=r.get("Priority", ""),
            description=r.get("Description", ""),
            activity_date=r.get("ActivityDate", ""),
            due_date=r.get("ActivityDate", ""),
            who_id=r.get("WhoId", ""),
            what_id=r.get("WhatId", ""),
            owner_name=self._extract_owner(r),
            is_completed=r.get("IsClosed", False) is True,
            created_date=r.get("CreatedDate", ""),
            raw_data=raw,
        )

    def map_event(self, raw: dict) -> Activity:
        r = self._apply_overrides("Event", raw)
        return Activity(
            sf_id=r.get("Id", ""),
            subject=r.get("Subject", ""),
            activity_type="event",
            status="completed" if r.get("EndDateTime") else "scheduled",
            priority="normal",
            description=r.get("Description", ""),
            activity_date=r.get("StartDateTime", r.get("ActivityDate", "")),
            due_date=r.get("EndDateTime", ""),
            who_id=r.get("WhoId", ""),
            what_id=r.get("WhatId", ""),
            owner_name=self._extract_owner(r),
            is_completed=False,
            created_date=r.get("CreatedDate", ""),
            raw_data=raw,
        )

    def _apply_overrides(self, object_type: str, raw: dict) -> dict:
        overrides = self._overrides.get(object_type, {})
        if not overrides:
            return raw
        remapped = dict(raw)
        for custom_field, standard_field in overrides.items():
            if custom_field in remapped:
                remapped[standard_field] = remapped.pop(custom_field)
        return remapped

    @staticmethod
    def _extract_owner(raw: dict) -> str:
        owner = raw.get("Owner")
        if isinstance(owner, dict):
            return owner.get("Name", "")
        return str(owner) if owner else ""

    @staticmethod
    def _safe_float(value) -> float | None:
        if value is None:
            return None
        try:
            return float(value)
        except (ValueError, TypeError):
            return None

    @staticmethod
    def _safe_int(value) -> int | None:
        if value is None:
            return None
        try:
            return int(value)
        except (ValueError, TypeError):
            return None
