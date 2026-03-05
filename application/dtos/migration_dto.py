"""
Migration DTOs

Structured schemas for migration configuration and results
passed between layers.
"""
from dataclasses import dataclass, field
from enum import Enum


class InputMode(Enum):
    API = "api"
    CSV = "csv"


class OutputMode(Enum):
    API = "api"
    FILE = "file"
    BOTH = "both"


class DuplicateStrategy(Enum):
    SKIP = "skip"
    OVERWRITE = "overwrite"
    KEEP_BOTH = "keep_both"


@dataclass(frozen=True)
class SalesforceApiConfig:
    username: str = ""
    password: str = ""
    security_token: str = ""
    domain: str = "login"
    client_id: str = ""
    client_secret: str = ""


@dataclass(frozen=True)
class CsvConfig:
    accounts_path: str = ""
    contacts_path: str = ""
    opportunities_path: str = ""
    tasks_path: str = ""
    events_path: str = ""


@dataclass(frozen=True)
class NexusApiConfig:
    base_url: str = ""
    api_key: str = ""
    batch_size: int = 50
    dry_run: bool = False


@dataclass(frozen=True)
class FileExportConfig:
    output_dir: str = "./output"
    formats: tuple[str, ...] = ("json",)


@dataclass(frozen=True)
class MigrationConfig:
    input_mode: InputMode = InputMode.CSV
    output_mode: OutputMode = OutputMode.FILE
    salesforce: SalesforceApiConfig = field(default_factory=SalesforceApiConfig)
    csv: CsvConfig = field(default_factory=CsvConfig)
    nexus_api: NexusApiConfig = field(default_factory=NexusApiConfig)
    file_export: FileExportConfig = field(default_factory=FileExportConfig)
    objects: tuple[str, ...] = ("accounts", "contacts", "opportunities", "activities")
    duplicate_strategy: DuplicateStrategy = DuplicateStrategy.SKIP
    field_overrides: dict = field(default_factory=dict)
    stage_overrides: dict = field(default_factory=dict)
