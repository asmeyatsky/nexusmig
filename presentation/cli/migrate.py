"""
Migration CLI -- Primary Interface

Architectural Intent:
- Presentation layer: thin CLI shell that delegates to application commands
- No business logic -- parses args, wires dependencies, calls use cases
- Supports: run, report, diff, quarantine, history, validate

Usage:
    python -m presentation.cli.migrate run --config migration.yaml
    python -m presentation.cli.migrate run --config migration.yaml --dry-run
    python -m presentation.cli.migrate report [--log <path>]
    python -m presentation.cli.migrate diff --baseline <log> --current <log>
    python -m presentation.cli.migrate quarantine [--log <path>] [--format csv]
    python -m presentation.cli.migrate history
    python -m presentation.cli.migrate validate --config migration.yaml
"""
import argparse
import asyncio
import sys
from dataclasses import replace
from pathlib import Path

from application.commands.export_quarantine import ExportQuarantineCommand
from application.commands.generate_diff_report import GenerateDiffReportCommand
from application.commands.generate_report import GenerateReportCommand
from application.commands.run_migration import RunMigrationCommand
from domain.ports.progress_ports import ProgressEvent
from domain.services.diff_service import DiffService
from infrastructure.config.dependency_injection import Container
from infrastructure.config.yaml_config import load_config
from infrastructure.logging.log_reader import LogReader
from infrastructure.logging.migration_logger import MigrationLogger
from infrastructure.logging.run_history import RunHistory


# ── Progress adapter (presentation layer) ──

class CliProgressAdapter:
    """Streams migration progress to stdout."""

    def __init__(self):
        self._last_line_len = 0

    def on_progress(self, event: ProgressEvent) -> None:
        if event.phase == "complete":
            self._clear_line()
            print(f"  {event.object_type}: {event.message}")
        else:
            msg = f"  [{event.phase}] {event.object_type}: {event.message}"
            self._clear_line()
            print(msg, end="\r", flush=True)
            self._last_line_len = len(msg)

    def _clear_line(self):
        if self._last_line_len:
            print(" " * self._last_line_len, end="\r", flush=True)
            self._last_line_len = 0


# ── Argument parser ──

def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="migrate",
        description="Salesforce -> Nexus CRM Migration Accelerator",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    # run
    run_p = sub.add_parser("run", help="Execute a migration")
    run_p.add_argument("--config", default="migration.yaml")
    run_p.add_argument("--dry-run", action="store_true", help="Validate without writing")
    run_p.add_argument("--no-progress", action="store_true", help="Disable progress output")

    # report
    report_p = sub.add_parser("report", help="Generate HTML report from a log file")
    report_p.add_argument("--log", default=None, help="Path to JSONL log (default: latest)")
    report_p.add_argument("--output", default=None, help="Output HTML path")

    # diff
    diff_p = sub.add_parser("diff", help="Compare two migration runs")
    diff_p.add_argument("--baseline", required=True, help="Baseline log file (e.g. dry-run)")
    diff_p.add_argument("--current", required=True, help="Current log file (e.g. live)")
    diff_p.add_argument("--output", default=None, help="Output HTML path")

    # quarantine
    quar_p = sub.add_parser("quarantine", help="Export quarantined records")
    quar_p.add_argument("--log", default=None, help="Path to JSONL log (default: latest)")
    quar_p.add_argument("--format", choices=["csv", "json"], default="csv")
    quar_p.add_argument("--output-dir", default="./output")

    # history
    sub.add_parser("history", help="Show past migration runs")

    # validate
    val_p = sub.add_parser("validate", help="Validate config and connectivity")
    val_p.add_argument("--config", default="migration.yaml")

    return parser


# ── Command handlers ──

async def _run_migration(args: argparse.Namespace) -> int:
    config = load_config(args.config)

    if args.dry_run:
        nexus = replace(config.nexus_api, dry_run=True)
        config = replace(config, nexus_api=nexus)

    progress = None if args.no_progress else CliProgressAdapter()

    container = Container(config)
    try:
        command = RunMigrationCommand(
            config=config,
            extractor=container.extractor(),
            loader=container.loader(),
            file_exporter=container.file_exporter(),
            progress=progress,
        )

        mode_label = "DRY RUN" if args.dry_run else "LIVE"
        print(f"Starting migration [{mode_label}] (input={config.input_mode.value}, output={config.output_mode.value})")
        print(f"Objects in scope: {', '.join(config.objects)}\n")

        summary = await command.execute()

        # Write log
        logger = MigrationLogger()
        log_path = logger.write_summary(summary)

        # Record in history
        history = RunHistory()
        config_hash = RunHistory.hash_config(args.config)
        history.record(
            summary=summary,
            log_path=log_path,
            config_hash=config_hash,
            input_mode=config.input_mode.value,
            output_mode=config.output_mode.value,
            dry_run=args.dry_run,
        )

        # Print summary
        print(f"\nMigration completed in {summary.duration_seconds:.1f}s")
        print(f"  Extracted:   {summary.total_extracted}")
        print(f"  Loaded:      {summary.total_loaded}")
        print(f"  Quarantined: {summary.total_quarantined}")
        print()
        for batch in summary.batches:
            print(f"  {batch.object_type}: {batch.success_count}/{batch.total} success, "
                  f"{batch.warning_count} warnings, {batch.error_count} errors")
        print(f"\nLog: {log_path}")

        if summary.warnings:
            print(f"\nWarnings ({len(summary.warnings)}):")
            for w in summary.warnings[:20]:
                print(f"  - {w}")
            if len(summary.warnings) > 20:
                print(f"  ... and {len(summary.warnings) - 20} more (see report)")

        # Generate report
        report_html = GenerateReportCommand(summary=summary).execute()
        report_path = Path(config.file_export.output_dir) / "migration_report.html"
        report_path.parent.mkdir(parents=True, exist_ok=True)
        report_path.write_text(report_html, encoding="utf-8")
        print(f"Report: {report_path}")

        # Export quarantine if any
        if summary.total_quarantined > 0:
            qpath = ExportQuarantineCommand(
                summary=summary, output_dir=config.file_export.output_dir, fmt="csv"
            ).execute()
            print(f"Quarantine export: {qpath}")

        return 0 if summary.total_quarantined == 0 else 1

    finally:
        await container.cleanup()


def _report(args: argparse.Namespace) -> int:
    reader = LogReader()
    log_path = args.log or reader.find_latest_log()
    if not log_path:
        print("No migration logs found. Run a migration first.", file=sys.stderr)
        return 1

    print(f"Reading log: {log_path}")
    summary = reader.read_summary(log_path)
    html = GenerateReportCommand(summary=summary).execute()

    output = args.output or "./output/migration_report.html"
    Path(output).parent.mkdir(parents=True, exist_ok=True)
    Path(output).write_text(html, encoding="utf-8")
    print(f"Report written to: {output}")
    return 0


def _diff(args: argparse.Namespace) -> int:
    reader = LogReader()
    baseline = reader.read_summary(args.baseline)
    current = reader.read_summary(args.current)

    diff_result = DiffService().compare(
        baseline, current,
        baseline_label=Path(args.baseline).stem,
        current_label=Path(args.current).stem,
    )

    html = GenerateDiffReportCommand(diff=diff_result).execute()

    output = args.output or "./output/migration_diff.html"
    Path(output).parent.mkdir(parents=True, exist_ok=True)
    Path(output).write_text(html, encoding="utf-8")

    status = "REGRESSION" if diff_result.is_regression else "OK"
    print(f"Diff: {status}")
    print(f"  Extracted: {diff_result.extracted_delta:+d}")
    print(f"  Loaded:    {diff_result.loaded_delta:+d}")
    print(f"  Quarantined: {diff_result.quarantined_delta:+d}")
    print(f"  Duration:  {diff_result.duration_delta:+.1f}s")
    print(f"Report: {output}")
    return 1 if diff_result.is_regression else 0


def _quarantine(args: argparse.Namespace) -> int:
    reader = LogReader()
    log_path = args.log or reader.find_latest_log()
    if not log_path:
        print("No migration logs found.", file=sys.stderr)
        return 1

    summary = reader.read_summary(log_path)
    if summary.total_quarantined == 0:
        print("No quarantined records found.")
        return 0

    path = ExportQuarantineCommand(
        summary=summary, output_dir=args.output_dir, fmt=args.format
    ).execute()
    print(f"Exported {summary.total_quarantined} quarantined records to: {path}")
    return 0


def _history(_args: argparse.Namespace) -> int:
    history = RunHistory()
    runs = history.list_runs(limit=20)
    if not runs:
        print("No migration runs recorded yet.")
        return 0

    print(f"{'Run ID':<32} {'Time':<22} {'Mode':<6} {'Extracted':>9} {'Loaded':>8} {'Quaran.':>8} {'Duration':>9} {'Status':<8}")
    print("-" * 115)
    for r in runs:
        ts = r.timestamp[:19].replace("T", " ")
        mode = "dry" if r.dry_run else "live"
        status = "OK" if r.success else "WARN"
        print(f"{r.run_id:<32} {ts:<22} {mode:<6} {r.total_extracted:>9} {r.total_loaded:>8} {r.total_quarantined:>8} {r.duration_seconds:>8.1f}s {status:<8}")
    return 0


def _validate(args: argparse.Namespace) -> int:
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

    handlers = {
        "run": lambda: asyncio.run(_run_migration(args)),
        "report": lambda: _report(args),
        "diff": lambda: _diff(args),
        "quarantine": lambda: _quarantine(args),
        "history": lambda: _history(args),
        "validate": lambda: _validate(args),
    }

    handler = handlers.get(args.command)
    if handler:
        sys.exit(handler())
    else:
        parser.print_help()
        sys.exit(1)


if __name__ == "__main__":
    main()
