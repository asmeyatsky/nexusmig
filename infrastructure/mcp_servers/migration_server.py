"""
Migration MCP Server

Architectural Intent:
- Exposes the migration-service bounded context as an MCP server
- Tools (write): run_migration, generate_report, export_quarantine
- Resources (read): migration status, run history, diff
- One MCP server per bounded context (per skill2026 Rule 6)
"""
import json

from mcp.server import Server

from application.commands.export_quarantine import ExportQuarantineCommand
from application.commands.generate_diff_report import GenerateDiffReportCommand
from application.commands.generate_report import GenerateReportCommand
from application.commands.run_migration import RunMigrationCommand
from application.queries.migration_status import MigrationStatusQuery
from domain.services.diff_service import DiffService
from domain.value_objects.migration_result import MigrationSummary
from infrastructure.config.dependency_injection import Container
from infrastructure.config.yaml_config import load_config
from infrastructure.logging.log_reader import LogReader
from infrastructure.logging.migration_logger import MigrationLogger
from infrastructure.logging.run_history import RunHistory


def create_migration_server() -> Server:
    server = Server("migration-service")
    _last_summary: dict[str, MigrationSummary | None] = {"value": None}

    @server.tool()
    async def run_migration(config_path: str = "migration.yaml", dry_run: bool = False) -> dict:
        """Execute a full Salesforce -> Nexus CRM migration.

        Args:
            config_path: Path to the migration YAML configuration file.
            dry_run: If true, validate payloads without writing data.

        Returns:
            Migration summary with per-object success/failure counts.
        """
        from dataclasses import replace as dreplace
        config = load_config(config_path)
        if dry_run:
            config = dreplace(config, nexus_api=dreplace(config.nexus_api, dry_run=True))

        container = Container(config)
        try:
            command = RunMigrationCommand(
                config=config,
                extractor=container.extractor(),
                loader=container.loader(),
                file_exporter=container.file_exporter(),
            )
            summary = await command.execute()
            _last_summary["value"] = summary

            logger = MigrationLogger()
            log_path = logger.write_summary(summary)
            history = RunHistory()
            history.record(summary=summary, log_path=log_path, dry_run=dry_run)

            return MigrationStatusQuery(summary=summary).execute()
        finally:
            await container.cleanup()

    @server.tool()
    async def generate_report(log_path: str = "") -> str:
        """Generate an HTML migration report.

        Args:
            log_path: Path to JSONL log file. If empty, uses last in-memory run.

        Returns:
            HTML report string.
        """
        if log_path:
            summary = LogReader().read_summary(log_path)
        elif _last_summary["value"]:
            summary = _last_summary["value"]
        else:
            return "<html><body><p>No migration has been run yet.</p></body></html>"
        return GenerateReportCommand(summary=summary).execute()

    @server.tool()
    async def export_quarantine(log_path: str = "", output_dir: str = "./output", fmt: str = "csv") -> str:
        """Export quarantined records to a file for remediation.

        Args:
            log_path: Path to JSONL log. If empty, uses last run.
            output_dir: Directory for the export file.
            fmt: Export format ('csv' or 'json').

        Returns:
            Path to the exported file.
        """
        if log_path:
            summary = LogReader().read_summary(log_path)
        elif _last_summary["value"]:
            summary = _last_summary["value"]
        else:
            return "No migration data available."
        return ExportQuarantineCommand(summary=summary, output_dir=output_dir, fmt=fmt).execute()

    @server.tool()
    async def compare_runs(baseline_log: str, current_log: str) -> str:
        """Compare two migration runs and generate a diff report.

        Args:
            baseline_log: Path to baseline JSONL log (e.g. dry-run).
            current_log: Path to current JSONL log (e.g. live run).

        Returns:
            HTML diff report.
        """
        reader = LogReader()
        baseline = reader.read_summary(baseline_log)
        current = reader.read_summary(current_log)
        diff = DiffService().compare(baseline, current)
        return GenerateDiffReportCommand(diff=diff).execute()

    @server.resource("migration://status")
    async def migration_status() -> str:
        """Current migration status and summary of the last run."""
        query = MigrationStatusQuery(summary=_last_summary["value"])
        return json.dumps(query.execute(), indent=2, default=str)

    @server.resource("migration://history")
    async def migration_history() -> str:
        """List of past migration runs with summary metrics."""
        history = RunHistory()
        runs = history.list_runs(limit=20)
        return json.dumps([r.to_dict() for r in runs], indent=2, default=str)

    return server
