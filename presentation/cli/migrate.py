"""
Migration CLI — Primary Interface

Architectural Intent:
- Presentation layer: thin CLI shell that delegates to application commands
- No business logic — parses args, wires dependencies, calls use cases
- Supports: run (execute migration), report (generate HTML report), validate (dry-run)

Usage:
    python -m presentation.cli.migrate run --config migration.yaml
    python -m presentation.cli.migrate run --config migration.yaml --dry-run
    python -m presentation.cli.migrate report --config migration.yaml
"""
import argparse
import asyncio
import sys
from pathlib import Path

from application.commands.generate_report import GenerateReportCommand
from application.commands.run_migration import RunMigrationCommand
from infrastructure.config.dependency_injection import Container
from infrastructure.config.yaml_config import load_config
from infrastructure.logging.migration_logger import MigrationLogger


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="migrate",
        description="Salesforce -> Nexus CRM Migration Accelerator",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    run_parser = sub.add_parser("run", help="Execute a migration")
    run_parser.add_argument("--config", default="migration.yaml", help="Path to config YAML")
    run_parser.add_argument("--dry-run", action="store_true", help="Validate without writing")

    report_parser = sub.add_parser("report", help="Generate HTML report from last run log")
    report_parser.add_argument("--config", default="migration.yaml", help="Path to config YAML")

    validate_parser = sub.add_parser("validate", help="Validate config and connectivity")
    validate_parser.add_argument("--config", default="migration.yaml", help="Path to config YAML")

    return parser


async def _run_migration(args: argparse.Namespace) -> int:
    config = load_config(args.config)

    if args.dry_run:
        from dataclasses import replace
        nexus = replace(config.nexus_api, dry_run=True)
        config = replace(config, nexus_api=nexus)

    container = Container(config)
    try:
        command = RunMigrationCommand(
            config=config,
            extractor=container.extractor(),
            loader=container.loader(),
            file_exporter=container.file_exporter(),
        )

        print(f"Starting migration (input={config.input_mode.value}, output={config.output_mode.value})")
        print(f"Objects in scope: {', '.join(config.objects)}")
        print()

        summary = await command.execute()

        logger = MigrationLogger()
        log_path = logger.write_summary(summary)

        print(f"Migration completed in {summary.duration_seconds:.1f}s")
        print(f"  Extracted:   {summary.total_extracted}")
        print(f"  Loaded:      {summary.total_loaded}")
        print(f"  Quarantined: {summary.total_quarantined}")
        print()
        for batch in summary.batches:
            print(f"  {batch.object_type}: {batch.success_count}/{batch.total} success, "
                  f"{batch.warning_count} warnings, {batch.error_count} errors")
        print(f"\nLog written to: {log_path}")

        if summary.warnings:
            print(f"\nWarnings ({len(summary.warnings)}):")
            for w in summary.warnings[:20]:
                print(f"  - {w}")

        report_html = GenerateReportCommand(summary=summary).execute()
        report_path = Path(config.file_export.output_dir) / "migration_report.html"
        report_path.parent.mkdir(parents=True, exist_ok=True)
        report_path.write_text(report_html, encoding="utf-8")
        print(f"Report written to: {report_path}")

        return 0 if summary.total_quarantined == 0 else 1

    finally:
        await container.cleanup()


async def _validate(args: argparse.Namespace) -> int:
    try:
        config = load_config(args.config)
        print(f"Configuration valid: {args.config}")
        print(f"  Input mode:  {config.input_mode.value}")
        print(f"  Output mode: {config.output_mode.value}")
        print(f"  Objects:     {', '.join(config.objects)}")
        return 0
    except Exception as e:
        print(f"Configuration error: {e}", file=sys.stderr)
        return 1


def main() -> None:
    parser = _build_parser()
    args = parser.parse_args()

    if args.command == "run":
        exit_code = asyncio.run(_run_migration(args))
    elif args.command == "report":
        exit_code = asyncio.run(_run_migration(args))
    elif args.command == "validate":
        exit_code = asyncio.run(_validate(args))
    else:
        parser.print_help()
        exit_code = 1

    sys.exit(exit_code)


if __name__ == "__main__":
    main()
