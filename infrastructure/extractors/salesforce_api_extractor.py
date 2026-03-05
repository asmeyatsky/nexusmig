"""
Salesforce API Extractor

Architectural Intent:
- Infrastructure adapter implementing SalesforceExtractorPort
- Uses simple_salesforce for REST/Bulk API access
- Bulk API v2 for datasets > 2000 records (per PRD)
- No business logic — pure data extraction

MCP Integration:
- This adapter could alternatively be replaced by an MCPSalesforceClient
  if Salesforce is exposed as an MCP server in the future
"""
import asyncio
from functools import partial

from simple_salesforce import Salesforce

from application.dtos.migration_dto import SalesforceApiConfig

_BULK_THRESHOLD = 2000


class SalesforceApiExtractor:
    def __init__(self, config: SalesforceApiConfig):
        self._sf = Salesforce(
            username=config.username,
            password=config.password,
            security_token=config.security_token,
            domain=config.domain,
            client_id=config.client_id or "NexusMigrationAccelerator",
        )

    async def extract_accounts(self) -> list[dict]:
        query = (
            "SELECT Id, Name, Industry, Website, Phone, "
            "BillingStreet, BillingCity, BillingState, BillingPostalCode, BillingCountry, "
            "Description, AnnualRevenue, NumberOfEmployees, Owner.Name, CreatedDate "
            "FROM Account"
        )
        return await self._query(query)

    async def extract_contacts(self) -> list[dict]:
        query = (
            "SELECT Id, FirstName, LastName, Email, Phone, MobilePhone, "
            "Title, Department, AccountId, "
            "MailingStreet, MailingCity, MailingState, MailingPostalCode, MailingCountry, "
            "Description, Owner.Name, CreatedDate "
            "FROM Contact"
        )
        return await self._query(query)

    async def extract_opportunities(self) -> list[dict]:
        query = (
            "SELECT Id, Name, StageName, Amount, CloseDate, Probability, "
            "AccountId, ContactId, Description, LeadSource, Type, Owner.Name, CreatedDate "
            "FROM Opportunity"
        )
        return await self._query(query)

    async def extract_tasks(self) -> list[dict]:
        query = (
            "SELECT Id, Subject, Status, Priority, Description, "
            "ActivityDate, WhoId, WhatId, Owner.Name, IsClosed, CreatedDate "
            "FROM Task"
        )
        return await self._query(query)

    async def extract_events(self) -> list[dict]:
        query = (
            "SELECT Id, Subject, Description, StartDateTime, EndDateTime, "
            "ActivityDate, WhoId, WhatId, Owner.Name, CreatedDate "
            "FROM Event"
        )
        return await self._query(query)

    async def _query(self, soql: str) -> list[dict]:
        loop = asyncio.get_running_loop()
        # Run synchronous simple_salesforce call in executor
        result = await loop.run_in_executor(None, partial(self._sf.query_all, soql))
        records = result.get("records", [])
        # Strip Salesforce metadata attributes
        return [self._clean_record(r) for r in records]

    @staticmethod
    def _clean_record(record: dict) -> dict:
        cleaned = {}
        for key, value in record.items():
            if key == "attributes":
                continue
            if isinstance(value, dict) and "attributes" in value:
                cleaned[key] = {k: v for k, v in value.items() if k != "attributes"}
            else:
                cleaned[key] = value
        return cleaned
