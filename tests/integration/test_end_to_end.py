"""
End-to-End Integration Test

Runs a full CSV -> File Export migration with real file I/O.
Verifies the complete pipeline: extract, map, transform, load, report.
"""
import json
import pytest
import tempfile
from pathlib import Path

from application.commands.run_migration import RunMigrationCommand
from application.commands.generate_report import GenerateReportCommand
from application.dtos.migration_dto import (
    CsvConfig, FileExportConfig, MigrationConfig, OutputMode,
)
from infrastructure.extractors.csv_extractor import CsvExtractor
from infrastructure.loaders.file_exporter import FileExporter


@pytest.fixture
def migration_env():
    with tempfile.TemporaryDirectory() as tmpdir:
        data_dir = Path(tmpdir) / "data"
        data_dir.mkdir()
        output_dir = Path(tmpdir) / "output"

        # Create sample CSV files
        (data_dir / "accounts.csv").write_text(
            "Id,Name,Industry,Website,Phone,BillingCity,BillingCountry\n"
            "001000000000001,Acme Corp,Technology,acme.com,555-0100,San Francisco,US\n"
            "001000000000002,Beta Inc,Finance,https://beta.io,555-0200,New York,US\n"
            "001000000000003,,Healthcare,,,,\n"  # Invalid — will be quarantined
        )
        (data_dir / "contacts.csv").write_text(
            "Id,FirstName,LastName,Email,Phone,AccountId\n"
            "003000000000001,John,Doe,JOHN@ACME.COM,555-1000,001000000000001\n"
            "003000000000002,Jane,Smith,jane@beta.io,555-2000,001000000000002\n"
        )
        (data_dir / "opportunities.csv").write_text(
            "Id,Name,StageName,Amount,CloseDate,AccountId\n"
            "006000000000001,Big Deal,Prospecting,100000,2024-06-30,001000000000001\n"
            "006000000000002,Small Deal,Closed Won,5000,2024-03-15,001000000000002\n"
        )
        (data_dir / "tasks.csv").write_text(
            "Id,Subject,Status,Priority,WhoId,WhatId\n"
            "00T000000000001,Follow up call,Not Started,High,003000000000001,006000000000001\n"
        )
        (data_dir / "events.csv").write_text(
            "Id,Subject,StartDateTime,EndDateTime,WhoId\n"
            "00U000000000001,Team Meeting,2024-01-15T10:00:00,2024-01-15T11:00:00,003000000000002\n"
        )

        config = MigrationConfig(
            output_mode=OutputMode.FILE,
            csv=CsvConfig(
                accounts_path=str(data_dir / "accounts.csv"),
                contacts_path=str(data_dir / "contacts.csv"),
                opportunities_path=str(data_dir / "opportunities.csv"),
                tasks_path=str(data_dir / "tasks.csv"),
                events_path=str(data_dir / "events.csv"),
            ),
            file_export=FileExportConfig(output_dir=str(output_dir), formats=("json", "csv")),
            objects=("accounts", "contacts", "opportunities", "activities"),
        )

        yield config, output_dir


class TestEndToEnd:
    @pytest.mark.asyncio
    async def test_full_csv_to_file_migration(self, migration_env):
        config, output_dir = migration_env
        extractor = CsvExtractor(config.csv)
        exporter = FileExporter(config.file_export.output_dir)

        command = RunMigrationCommand(
            config=config,
            extractor=extractor,
            loader=None,
            file_exporter=exporter,
        )

        summary = await command.execute()

        # 3 accounts + 2 contacts + 2 opportunities + (1 task + 1 event) = 9 raw extracted
        assert summary.total_extracted == 9
        assert summary.total_quarantined == 1  # Account with empty name
        assert summary.total_loaded == 8  # 9 - 1 quarantined

        # Verify output files exist
        assert (output_dir / "companies.json").exists()
        assert (output_dir / "contacts.json").exists()
        assert (output_dir / "deals.json").exists()
        assert (output_dir / "activities.json").exists()

        # Verify JSON content
        companies = json.loads((output_dir / "companies.json").read_text())
        assert len(companies) == 2  # 3 extracted, 1 quarantined
        assert companies[0]["name"] == "Acme Corp"
        assert companies[0]["website"] == "https://acme.com"  # URL normalised

        contacts = json.loads((output_dir / "contacts.json").read_text())
        assert len(contacts) == 2
        assert contacts[0]["email"] == "john@acme.com"  # Lowercased

        deals = json.loads((output_dir / "deals.json").read_text())
        assert len(deals) == 2
        assert deals[0]["stage"] == "Discovery"  # Mapped from Prospecting
        assert deals[1]["stage"] == "Won"  # Mapped from Closed Won

        activities = json.loads((output_dir / "activities.json").read_text())
        assert len(activities) == 2

    @pytest.mark.asyncio
    async def test_report_generation(self, migration_env):
        config, output_dir = migration_env
        extractor = CsvExtractor(config.csv)
        exporter = FileExporter(config.file_export.output_dir)

        command = RunMigrationCommand(
            config=config, extractor=extractor,
            loader=None, file_exporter=exporter,
        )
        summary = await command.execute()

        html = GenerateReportCommand(summary=summary).execute()
        assert "Migration Report" in html
        assert "Quarantined" in html
        assert "Account" in html
