"""
Dependency Injection — Composition Root

Architectural Intent:
- Wires infrastructure adapters to domain ports based on configuration
- Single place where concrete implementations are chosen
- No business logic — pure wiring
"""
from application.dtos.migration_dto import InputMode, MigrationConfig, OutputMode
from infrastructure.extractors.csv_extractor import CsvExtractor
from infrastructure.extractors.salesforce_api_extractor import SalesforceApiExtractor
from infrastructure.loaders.file_exporter import FileExporter
from infrastructure.loaders.nexus_api_loader import NexusApiLoader


class Container:
    def __init__(self, config: MigrationConfig):
        self._config = config
        self._loader: NexusApiLoader | None = None

    def extractor(self):
        if self._config.input_mode == InputMode.API:
            return SalesforceApiExtractor(self._config.salesforce)
        return CsvExtractor(self._config.csv)

    def loader(self) -> NexusApiLoader | None:
        if self._config.output_mode in (OutputMode.API, OutputMode.BOTH):
            self._loader = NexusApiLoader(self._config.nexus_api)
            return self._loader
        return None

    def file_exporter(self) -> FileExporter | None:
        if self._config.output_mode in (OutputMode.FILE, OutputMode.BOTH):
            return FileExporter(self._config.file_export.output_dir)
        return None

    async def cleanup(self) -> None:
        if self._loader:
            await self._loader.close()
