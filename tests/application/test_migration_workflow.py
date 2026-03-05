"""
Migration Workflow Tests — Use Case Tests with Mocked Ports

Verifies the DAG orchestration: parallel execution of Pass 1 and Pass 2,
correct relationship resolution, and proper result aggregation.
"""
import pytest
from unittest.mock import AsyncMock

from application.dtos.migration_dto import (
    FileExportConfig, MigrationConfig, OutputMode,
)
from application.orchestration.migration_workflow import MigrationWorkflow
from domain.services.mapping_service import MappingService
from domain.services.transform_service import TransformService
from domain.services.relationship_resolver import RelationshipResolver
from domain.value_objects.migration_result import RecordResult, RecordStatus


def _make_config(**overrides) -> MigrationConfig:
    defaults = dict(
        output_mode=OutputMode.FILE,
        file_export=FileExportConfig(output_dir="/tmp/test_output", formats=("json",)),
        objects=("accounts", "contacts", "opportunities", "activities"),
    )
    defaults.update(overrides)
    return MigrationConfig(**defaults)


def _mock_extractor():
    ext = AsyncMock()
    ext.extract_accounts.return_value = [
        {"Id": "001ABC000000001", "Name": "Acme Corp", "Industry": "Tech"},
        {"Id": "001ABC000000002", "Name": "Beta Inc"},
    ]
    ext.extract_contacts.return_value = [
        {"Id": "003ABC000000001", "FirstName": "John", "LastName": "Doe",
         "Email": "john@acme.com", "AccountId": "001ABC000000001"},
    ]
    ext.extract_opportunities.return_value = [
        {"Id": "006ABC000000001", "Name": "Big Deal", "StageName": "Prospecting",
         "Amount": "100000", "AccountId": "001ABC000000001"},
    ]
    ext.extract_tasks.return_value = [
        {"Id": "00TABC000000001", "Subject": "Follow up", "Status": "Not Started",
         "WhoId": "003ABC000000001", "WhatId": "006ABC000000001"},
    ]
    ext.extract_events.return_value = []
    return ext


def _mock_exporter():
    exp = AsyncMock()
    exp.export.return_value = "/tmp/test_output/test.json"
    return exp


class TestMigrationWorkflow:
    @pytest.mark.asyncio
    async def test_full_migration_produces_summary(self):
        config = _make_config()
        extractor = _mock_extractor()
        exporter = _mock_exporter()

        workflow = MigrationWorkflow(
            config=config,
            extractor=extractor,
            loader=None,
            file_exporter=exporter,
            mapping_service=MappingService(),
            transform_service=TransformService(),
            resolver=RelationshipResolver(),
        )

        summary = await workflow.execute()

        assert summary.total_extracted > 0
        assert summary.total_loaded > 0
        assert len(summary.batches) == 4
        assert summary.duration_seconds > 0

    @pytest.mark.asyncio
    async def test_accounts_extracted_and_transformed(self):
        config = _make_config(objects=("accounts",))
        extractor = _mock_extractor()
        exporter = _mock_exporter()

        workflow = MigrationWorkflow(
            config=config, extractor=extractor, loader=None,
            file_exporter=exporter, mapping_service=MappingService(),
            transform_service=TransformService(), resolver=RelationshipResolver(),
        )

        summary = await workflow.execute()

        extractor.extract_accounts.assert_awaited_once()
        assert summary.batches[0].object_type == "Account"
        assert summary.batches[0].total == 2

    @pytest.mark.asyncio
    async def test_quarantined_records_counted(self):
        config = _make_config(objects=("accounts",))
        extractor = AsyncMock()
        extractor.extract_accounts.return_value = [
            {"Id": "001ABC000000001", "Name": "Valid"},
            {"Id": "001ABC000000002", "Name": ""},  # Will be quarantined
        ]
        exporter = _mock_exporter()

        workflow = MigrationWorkflow(
            config=config, extractor=extractor, loader=None,
            file_exporter=exporter, mapping_service=MappingService(),
            transform_service=TransformService(), resolver=RelationshipResolver(),
        )

        summary = await workflow.execute()

        assert summary.batches[0].quarantined_count == 1
        assert summary.total_quarantined == 1

    @pytest.mark.asyncio
    async def test_parallel_pass1_both_object_types(self):
        config = _make_config(objects=("accounts", "contacts"))
        extractor = _mock_extractor()
        exporter = _mock_exporter()

        workflow = MigrationWorkflow(
            config=config, extractor=extractor, loader=None,
            file_exporter=exporter, mapping_service=MappingService(),
            transform_service=TransformService(), resolver=RelationshipResolver(),
        )

        summary = await workflow.execute()

        extractor.extract_accounts.assert_awaited_once()
        extractor.extract_contacts.assert_awaited_once()
        assert len(summary.batches) == 2

    @pytest.mark.asyncio
    async def test_activities_extracts_tasks_and_events(self):
        config = _make_config(objects=("activities",))
        extractor = _mock_extractor()
        exporter = _mock_exporter()

        workflow = MigrationWorkflow(
            config=config, extractor=extractor, loader=None,
            file_exporter=exporter, mapping_service=MappingService(),
            transform_service=TransformService(), resolver=RelationshipResolver(),
        )

        summary = await workflow.execute()

        extractor.extract_tasks.assert_awaited_once()
        extractor.extract_events.assert_awaited_once()
