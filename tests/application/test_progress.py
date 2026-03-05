"""
Progress Callback Tests

Verifies that progress events are emitted during workflow execution.
"""
import pytest
from unittest.mock import AsyncMock

from application.commands.run_migration import RunMigrationCommand
from application.dtos.migration_dto import FileExportConfig, MigrationConfig, OutputMode
from domain.ports.progress_ports import ProgressEvent


class MockProgress:
    def __init__(self):
        self.events: list[ProgressEvent] = []

    def on_progress(self, event: ProgressEvent) -> None:
        self.events.append(event)


class TestProgressCallbacks:
    @pytest.mark.asyncio
    async def test_progress_events_emitted(self):
        extractor = AsyncMock()
        extractor.extract_accounts.return_value = [
            {"Id": "001ABC000000001", "Name": "Acme"},
        ]
        extractor.extract_contacts.return_value = []
        extractor.extract_opportunities.return_value = []
        extractor.extract_tasks.return_value = []
        extractor.extract_events.return_value = []

        exporter = AsyncMock()
        exporter.export.return_value = "/tmp/test.json"

        progress = MockProgress()
        config = MigrationConfig(
            output_mode=OutputMode.FILE,
            file_export=FileExportConfig(output_dir="/tmp/test", formats=("json",)),
            objects=("accounts",),
        )

        command = RunMigrationCommand(
            config=config, extractor=extractor,
            loader=None, file_exporter=exporter,
            progress=progress,
        )
        await command.execute()

        assert len(progress.events) > 0
        phases = [e.phase for e in progress.events]
        assert "extract" in phases
        assert "complete" in phases
        assert all(e.object_type == "Account" for e in progress.events)

    @pytest.mark.asyncio
    async def test_no_progress_still_works(self):
        """Migration works fine without a progress adapter (None)."""
        extractor = AsyncMock()
        extractor.extract_accounts.return_value = [{"Id": "001", "Name": "Test"}]
        extractor.extract_contacts.return_value = []
        exporter = AsyncMock()
        exporter.export.return_value = "/tmp/t.json"

        config = MigrationConfig(
            output_mode=OutputMode.FILE,
            file_export=FileExportConfig(output_dir="/tmp/t", formats=("json",)),
            objects=("accounts",),
        )

        command = RunMigrationCommand(
            config=config, extractor=extractor,
            loader=None, file_exporter=exporter,
            progress=None,
        )
        summary = await command.execute()
        assert summary.total_extracted == 1
