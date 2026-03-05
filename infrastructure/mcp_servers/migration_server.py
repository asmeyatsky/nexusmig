"""
Migration MCP Server

Architectural Intent:
- Exposes the migration-service bounded context as an MCP server
- Tools (write operations): run_migration, generate_report
- Resources (read operations): migration status, last run summary
- One MCP server per bounded context (per skill2026 Rule 6)

MCP Integration:
- Tools map to application-layer use cases
- Resources map to query handlers
- All schemas are typed and documented
"""
from mcp.server import Server

from application.commands.generate_report import GenerateReportCommand
from application.commands.run_migration import RunMigrationCommand
from application.queries.migration_status import MigrationStatusQuery
from domain.value_objects.migration_result import MigrationSummary
from infrastructure.config.dependency_injection import Container
from infrastructure.config.yaml_config import load_config


def create_migration_server() -> Server:
    server = Server("migration-service")
    _last_summary: dict[str, MigrationSummary | None] = {"value": None}

    @server.tool()
    async def run_migration(config_path: str = "migration.yaml") -> dict:
        """Execute a full Salesforce -> Nexus CRM migration.

        Args:
            config_path: Path to the migration YAML configuration file.

        Returns:
            Migration summary with per-object success/failure counts.
        """
        config = load_config(config_path)
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
            return MigrationStatusQuery(summary=summary).execute()
        finally:
            await container.cleanup()

    @server.tool()
    async def generate_report() -> str:
        """Generate an HTML migration report from the last run.

        Returns:
            HTML string of the migration report, or error if no run exists.
        """
        summary = _last_summary["value"]
        if not summary:
            return "<html><body><p>No migration has been run yet.</p></body></html>"
        return GenerateReportCommand(summary=summary).execute()

    @server.resource("migration://status")
    async def migration_status() -> str:
        """Current migration status and summary of the last run."""
        import json
        query = MigrationStatusQuery(summary=_last_summary["value"])
        return json.dumps(query.execute(), indent=2, default=str)

    return server
