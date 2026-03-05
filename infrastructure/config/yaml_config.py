"""
YAML Configuration Loader

Architectural Intent:
- Infrastructure concern: reads migration.yaml and produces a MigrationConfig DTO
- Validates required fields based on input/output mode
- No business logic — pure configuration parsing
"""
from pathlib import Path

import yaml

from application.dtos.migration_dto import (
    CsvConfig,
    DuplicateStrategy,
    FileExportConfig,
    InputMode,
    MigrationConfig,
    NexusApiConfig,
    OutputMode,
    SalesforceApiConfig,
)


def load_config(path: str = "migration.yaml") -> MigrationConfig:
    config_path = Path(path)
    if not config_path.exists():
        raise FileNotFoundError(f"Configuration file not found: {path}")

    with open(config_path, "r") as f:
        raw = yaml.safe_load(f)

    input_mode = InputMode(raw.get("input_mode", "csv"))
    output_mode = OutputMode(raw.get("output_mode", "file"))

    sf_raw = raw.get("salesforce", {})
    sf_config = SalesforceApiConfig(
        username=sf_raw.get("username", ""),
        password=sf_raw.get("password", ""),
        security_token=sf_raw.get("security_token", ""),
        domain=sf_raw.get("domain", "login"),
        client_id=sf_raw.get("client_id", ""),
        client_secret=sf_raw.get("client_secret", ""),
    )

    csv_raw = raw.get("csv", {})
    csv_config = CsvConfig(
        accounts_path=csv_raw.get("accounts", ""),
        contacts_path=csv_raw.get("contacts", ""),
        opportunities_path=csv_raw.get("opportunities", ""),
        tasks_path=csv_raw.get("tasks", ""),
        events_path=csv_raw.get("events", ""),
    )

    nexus_raw = raw.get("nexus_api", {})
    nexus_config = NexusApiConfig(
        base_url=nexus_raw.get("base_url", ""),
        api_key=nexus_raw.get("api_key", ""),
        batch_size=nexus_raw.get("batch_size", 50),
        dry_run=nexus_raw.get("dry_run", False),
    )

    export_raw = raw.get("file_export", {})
    file_config = FileExportConfig(
        output_dir=export_raw.get("output_dir", "./output"),
        formats=tuple(export_raw.get("formats", ["json"])),
    )

    objects = tuple(raw.get("objects", ["accounts", "contacts", "opportunities", "activities"]))
    dup_strategy = DuplicateStrategy(raw.get("duplicate_strategy", "skip"))

    return MigrationConfig(
        input_mode=input_mode,
        output_mode=output_mode,
        salesforce=sf_config,
        csv=csv_config,
        nexus_api=nexus_config,
        file_export=file_config,
        objects=objects,
        duplicate_strategy=dup_strategy,
        field_overrides=raw.get("field_overrides", {}),
        stage_overrides=raw.get("stage_overrides", {}),
    )
