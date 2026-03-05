"""
Run Migration Command

Architectural Intent:
- Single use case: execute a full Salesforce -> Nexus migration
- Orchestrates domain services via ports — no infrastructure knowledge
- Delegates to DAG orchestrator for parallel execution

MCP Integration:
- Exposed as 'run_migration' tool on the migration-service MCP server

Parallelization Notes:
- Pass 1 (Accounts + Contacts): extracted and transformed in parallel
- Pass 2 (Opportunities + Activities): extracted/transformed in parallel, after Pass 1 load
- Loading per object type is sequential (batch API calls), but object types load in parallel
"""
from dataclasses import dataclass, field

from application.dtos.migration_dto import MigrationConfig
from application.orchestration.migration_workflow import MigrationWorkflow
from domain.value_objects.migration_result import MigrationSummary
from domain.ports.extractor_ports import SalesforceExtractorPort
from domain.ports.loader_ports import NexusLoaderPort, FileExporterPort
from domain.ports.progress_ports import ProgressPort
from domain.services.mapping_service import MappingService
from domain.services.transform_service import TransformService
from domain.services.relationship_resolver import RelationshipResolver


@dataclass
class RunMigrationCommand:
    config: MigrationConfig
    extractor: SalesforceExtractorPort
    loader: NexusLoaderPort | None
    file_exporter: FileExporterPort | None
    progress: ProgressPort | None = None

    async def execute(self) -> MigrationSummary:
        mapping_service = MappingService(field_overrides=self.config.field_overrides)
        transform_service = TransformService()
        resolver = RelationshipResolver()

        workflow = MigrationWorkflow(
            config=self.config,
            extractor=self.extractor,
            loader=self.loader,
            file_exporter=self.file_exporter,
            mapping_service=mapping_service,
            transform_service=transform_service,
            resolver=resolver,
            progress=self.progress,
        )
        return await workflow.execute()
