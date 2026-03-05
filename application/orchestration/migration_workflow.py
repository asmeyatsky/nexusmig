"""
Migration Workflow — DAG-Based Orchestration

Architectural Intent:
- Implements the two-pass migration strategy as a dependency DAG
- Pass 1 (Accounts + Contacts): extract, transform, load in parallel
- Pass 2 (Opportunities + Activities): extract, transform, load in parallel (depends on Pass 1)
- Uses asyncio.gather for fan-out/fan-in within each pass
- Backpressure is applied at the loader level (batch size config)

Parallelization Notes:
- Account extraction ∥ Contact extraction (no dependency)
- Opportunity extraction ∥ Activity extraction (no dependency)
- Pass 2 depends on Pass 1 completion (relationship lookup table)
- File export ∥ API push (independent output targets)
"""
import asyncio
import time
from dataclasses import dataclass

from application.dtos.migration_dto import MigrationConfig, OutputMode
from domain.entities.account import Account
from domain.entities.contact import Contact
from domain.entities.opportunity import Opportunity
from domain.entities.activity import Activity
from domain.ports.extractor_ports import SalesforceExtractorPort
from domain.ports.loader_ports import NexusLoaderPort, FileExporterPort
from domain.services.mapping_service import MappingService
from domain.services.transform_service import TransformService
from domain.services.relationship_resolver import RelationshipResolver
from domain.value_objects.errors import ValidationError
from domain.value_objects.migration_result import (
    BatchResult,
    MigrationSummary,
    RecordResult,
    RecordStatus,
)


@dataclass
class MigrationWorkflow:
    config: MigrationConfig
    extractor: SalesforceExtractorPort
    loader: NexusLoaderPort | None
    file_exporter: FileExporterPort | None
    mapping_service: MappingService
    transform_service: TransformService
    resolver: RelationshipResolver

    async def execute(self) -> MigrationSummary:
        start = time.monotonic()
        batches: list[BatchResult] = []
        all_warnings: list[str] = []
        total_extracted = 0
        total_loaded = 0
        total_quarantined = 0

        # ── Pass 1: Accounts & Contacts (parallel extraction + transform) ──
        pass1_tasks = []
        if "accounts" in self.config.objects:
            pass1_tasks.append(self._process_accounts())
        if "contacts" in self.config.objects:
            pass1_tasks.append(self._process_contacts())

        if pass1_tasks:
            pass1_results = await asyncio.gather(*pass1_tasks)
            for batch in pass1_results:
                batches.append(batch)
                total_extracted += batch.total
                total_loaded += batch.success_count
                total_quarantined += batch.quarantined_count

        # ── Pass 2: Opportunities & Activities (depend on Pass 1 lookup table) ──
        pass2_tasks = []
        if "opportunities" in self.config.objects:
            pass2_tasks.append(self._process_opportunities())
        if "activities" in self.config.objects:
            pass2_tasks.append(self._process_activities())

        if pass2_tasks:
            pass2_results = await asyncio.gather(*pass2_tasks)
            for batch in pass2_results:
                batches.append(batch)
                total_extracted += batch.total
                total_loaded += batch.success_count
                total_quarantined += batch.quarantined_count

        # Collect unresolved relationship warnings
        for w in self.resolver.unresolved_warnings:
            all_warnings.append(w.message)

        duration = time.monotonic() - start
        return MigrationSummary(
            batches=tuple(batches),
            total_extracted=total_extracted,
            total_loaded=total_loaded,
            total_quarantined=total_quarantined,
            duration_seconds=duration,
            warnings=tuple(all_warnings),
        )

    async def _process_accounts(self) -> BatchResult:
        raw_records = await self.extractor.extract_accounts()
        accounts: list[Account] = []
        quarantined: list[RecordResult] = []
        warnings: list[RecordResult] = []

        for raw in raw_records:
            account = self.mapping_service.map_account(raw)
            try:
                account = account.validate()
            except ValidationError as e:
                quarantined.append(RecordResult(
                    salesforce_id=account.sf_id, object_type="Account",
                    status=RecordStatus.QUARANTINED, message=str(e),
                ))
                continue
            transformed, tw = self.transform_service.transform_account(account)
            warnings.extend(tw)
            accounts.append(transformed)

        dup_warnings = self.transform_service.detect_duplicate_accounts(accounts)
        warnings.extend(dup_warnings)

        nexus_records = [a.to_nexus_company() for a in accounts]
        load_results = await self._load_and_export("companies", nexus_records)

        for result in load_results:
            if result.nexus_id and result.salesforce_id:
                self.resolver.register(result.salesforce_id, result.nexus_id)

        return self._build_batch("Account", len(raw_records), load_results, quarantined, warnings)

    async def _process_contacts(self) -> BatchResult:
        raw_records = await self.extractor.extract_contacts()
        contacts: list[Contact] = []
        quarantined: list[RecordResult] = []
        warnings: list[RecordResult] = []

        for raw in raw_records:
            contact = self.mapping_service.map_contact(raw)
            try:
                contact = contact.validate()
            except ValidationError as e:
                quarantined.append(RecordResult(
                    salesforce_id=contact.sf_id, object_type="Contact",
                    status=RecordStatus.QUARANTINED, message=str(e),
                ))
                continue
            transformed, tw = self.transform_service.transform_contact(contact)
            warnings.extend(tw)
            contacts.append(transformed)

        dup_warnings = self.transform_service.detect_duplicate_contacts(contacts)
        warnings.extend(dup_warnings)

        nexus_records = []
        for c in contacts:
            account_nexus_id = self.resolver.resolve(c.account_sf_id, "Contact->Account")
            nexus_records.append(c.to_nexus_contact(account_nexus_id))

        load_results = await self._load_and_export("contacts", nexus_records)

        for result in load_results:
            if result.nexus_id and result.salesforce_id:
                self.resolver.register(result.salesforce_id, result.nexus_id)

        return self._build_batch("Contact", len(raw_records), load_results, quarantined, warnings)

    async def _process_opportunities(self) -> BatchResult:
        raw_records = await self.extractor.extract_opportunities()
        opportunities: list[Opportunity] = []
        quarantined: list[RecordResult] = []
        warnings: list[RecordResult] = []

        for raw in raw_records:
            opp = self.mapping_service.map_opportunity(raw)
            try:
                opp = opp.validate()
            except ValidationError as e:
                quarantined.append(RecordResult(
                    salesforce_id=opp.sf_id, object_type="Opportunity",
                    status=RecordStatus.QUARANTINED, message=str(e),
                ))
                continue
            transformed, tw = self.transform_service.transform_opportunity(opp)
            warnings.extend(tw)
            opportunities.append(transformed)

        stage_map = self.config.stage_overrides or None
        nexus_records = []
        for o in opportunities:
            account_nexus_id = self.resolver.resolve(o.account_sf_id, "Opportunity->Account")
            contact_nexus_id = self.resolver.resolve(o.contact_sf_id, "Opportunity->Contact")
            nexus_records.append(o.to_nexus_deal(account_nexus_id, contact_nexus_id, stage_map))

        load_results = await self._load_and_export("deals", nexus_records)
        return self._build_batch("Opportunity", len(raw_records), load_results, quarantined, warnings)

    async def _process_activities(self) -> BatchResult:
        task_raw, event_raw = await asyncio.gather(
            self.extractor.extract_tasks(),
            self.extractor.extract_events(),
        )
        activities: list[Activity] = []
        quarantined: list[RecordResult] = []
        warnings: list[RecordResult] = []

        for raw in task_raw:
            activity = self.mapping_service.map_task(raw)
            try:
                activity = activity.validate()
            except ValidationError as e:
                quarantined.append(RecordResult(
                    salesforce_id=activity.sf_id, object_type="Activity",
                    status=RecordStatus.QUARANTINED, message=str(e),
                ))
                continue
            transformed, tw = self.transform_service.transform_activity(activity)
            warnings.extend(tw)
            activities.append(transformed)

        for raw in event_raw:
            activity = self.mapping_service.map_event(raw)
            try:
                activity = activity.validate()
            except ValidationError as e:
                quarantined.append(RecordResult(
                    salesforce_id=activity.sf_id, object_type="Activity",
                    status=RecordStatus.QUARANTINED, message=str(e),
                ))
                continue
            transformed, tw = self.transform_service.transform_activity(activity)
            warnings.extend(tw)
            activities.append(transformed)

        nexus_records = []
        for a in activities:
            related_id = self.resolver.resolve(a.what_id, "Activity->WhatId")
            contact_id = self.resolver.resolve(a.who_id, "Activity->WhoId")
            nexus_records.append(a.to_nexus_activity(related_id, contact_id))

        load_results = await self._load_and_export("activities", nexus_records)
        total_raw = len(task_raw) + len(event_raw)
        return self._build_batch("Activity", total_raw, load_results, quarantined, warnings)

    async def _load_and_export(
        self, object_type: str, records: list[dict]
    ) -> list[RecordResult]:
        load_results: list[RecordResult] = []
        tasks = []

        should_api = self.config.output_mode in (OutputMode.API, OutputMode.BOTH)
        should_file = self.config.output_mode in (OutputMode.FILE, OutputMode.BOTH)

        if should_api and self.loader:
            loader_method = getattr(self.loader, f"load_{object_type}")
            tasks.append(loader_method(records))

        if should_file and self.file_exporter:
            for fmt in self.config.file_export.formats:
                tasks.append(self.file_exporter.export(object_type, records, fmt))

        results = await asyncio.gather(*tasks, return_exceptions=True)

        for result in results:
            if isinstance(result, Exception):
                load_results.append(RecordResult(
                    salesforce_id="", object_type=object_type,
                    status=RecordStatus.ERROR, message=str(result),
                ))
            elif isinstance(result, list):
                load_results.extend(result)
            # File export returns a path string — no RecordResults needed

        if not load_results:
            load_results = [
                RecordResult(
                    salesforce_id=r.get("external_id", ""),
                    object_type=object_type,
                    status=RecordStatus.SUCCESS,
                )
                for r in records
            ]

        return load_results

    @staticmethod
    def _build_batch(
        object_type: str,
        total_raw: int,
        load_results: list[RecordResult],
        quarantined: list[RecordResult],
        warnings: list[RecordResult],
    ) -> BatchResult:
        success = sum(1 for r in load_results if r.status == RecordStatus.SUCCESS)
        errors = sum(1 for r in load_results if r.status == RecordStatus.ERROR)
        all_results = tuple(load_results) + tuple(quarantined) + tuple(warnings)
        return BatchResult(
            object_type=object_type,
            total=total_raw,
            success_count=success,
            warning_count=len(warnings),
            error_count=errors,
            quarantined_count=len(quarantined),
            record_results=all_results,
        )
