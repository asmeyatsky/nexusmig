"""
Migration Web UI — FastAPI Application

Architectural Intent:
- Presentation layer: web interface for non-technical users
- Delegates to the same application commands as the CLI
- SSE endpoint for real-time progress streaming
- No business logic — pure HTTP handling and template rendering

Usage:
    python -m presentation.web.app
    # or: uvicorn presentation.web.app:app --reload
"""
import asyncio
import json
import shutil
import tempfile
import uuid
from dataclasses import replace
from pathlib import Path

from fastapi import FastAPI, File, Form, Request, UploadFile
from fastapi.responses import HTMLResponse, JSONResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from application.commands.export_quarantine import ExportQuarantineCommand
from application.commands.generate_diff_report import GenerateDiffReportCommand
from application.commands.generate_report import GenerateReportCommand
from application.commands.run_migration import RunMigrationCommand
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
from domain.ports.progress_ports import ProgressEvent
from domain.services.diff_service import DiffService
from infrastructure.config.dependency_injection import Container
from infrastructure.logging.log_reader import LogReader
from infrastructure.logging.migration_logger import MigrationLogger
from infrastructure.logging.run_history import RunHistory

_WEB_DIR = Path(__file__).parent
_UPLOAD_DIR = Path(tempfile.gettempdir()) / "nexusmig_uploads"
_OUTPUT_DIR = Path("./output")

app = FastAPI(title="Nexus Migration Accelerator")
app.mount("/static", StaticFiles(directory=str(_WEB_DIR / "static")), name="static")
templates = Jinja2Templates(directory=str(_WEB_DIR / "templates"))

# In-memory store for active migration progress
_active_runs: dict[str, list[ProgressEvent]] = {}
_run_complete: dict[str, bool] = {}


class WebProgressAdapter:
    """Collects progress events for SSE streaming."""

    def __init__(self, run_id: str):
        self.run_id = run_id
        _active_runs[run_id] = []
        _run_complete[run_id] = False

    def on_progress(self, event: ProgressEvent) -> None:
        _active_runs[self.run_id].append(event)


# ── Pages ──

@app.get("/", response_class=HTMLResponse)
async def index(request: Request):
    history = RunHistory()
    runs = history.list_runs(limit=10)
    return templates.TemplateResponse("index.html", {"request": request, "runs": runs})


# ── API: Migration ──

@app.post("/api/upload-csv")
async def upload_csv(
    accounts: UploadFile | None = File(None),
    contacts: UploadFile | None = File(None),
    opportunities: UploadFile | None = File(None),
    tasks: UploadFile | None = File(None),
    events: UploadFile | None = File(None),
):
    session_id = uuid.uuid4().hex[:12]
    session_dir = _UPLOAD_DIR / session_id
    session_dir.mkdir(parents=True, exist_ok=True)

    paths = {}
    for name, file in [("accounts", accounts), ("contacts", contacts),
                        ("opportunities", opportunities), ("tasks", tasks),
                        ("events", events)]:
        if file and file.filename:
            dest = session_dir / f"{name}.csv"
            content = await file.read()
            dest.write_bytes(content)
            paths[name] = str(dest)

    return {"session_id": session_id, "uploaded": list(paths.keys()), "paths": paths}


@app.post("/api/run")
async def run_migration(request: Request):
    body = await request.json()
    run_id = uuid.uuid4().hex[:12]

    config = _build_config(body)
    progress = WebProgressAdapter(run_id)

    # Run in background task
    asyncio.create_task(_execute_migration(run_id, config, progress, body.get("dry_run", False)))

    return {"run_id": run_id}


@app.get("/api/progress/{run_id}")
async def progress_stream(run_id: str):
    async def event_generator():
        cursor = 0
        while True:
            events = _active_runs.get(run_id, [])
            while cursor < len(events):
                e = events[cursor]
                data = json.dumps({
                    "phase": e.phase, "object_type": e.object_type,
                    "current": e.current, "total": e.total, "message": e.message,
                })
                yield f"data: {data}\n\n"
                cursor += 1

            if _run_complete.get(run_id):
                yield f"data: {json.dumps({'phase': 'done'})}\n\n"
                break

            await asyncio.sleep(0.1)

    return StreamingResponse(event_generator(), media_type="text/event-stream")


@app.get("/api/result/{run_id}")
async def get_result(run_id: str):
    history = RunHistory()
    for entry in history.list_runs(limit=50):
        if entry.run_id == run_id:
            return entry.to_dict()
    return JSONResponse({"error": "Run not found"}, status_code=404)


@app.get("/api/history")
async def get_history():
    history = RunHistory()
    return [r.to_dict() for r in history.list_runs(limit=50)]


@app.get("/api/report/{run_id}", response_class=HTMLResponse)
async def get_report(run_id: str):
    history = RunHistory()
    entry = history.get_run(run_id)
    if not entry:
        return HTMLResponse("<p>Run not found</p>", status_code=404)

    reader = LogReader()
    summary = reader.read_summary(entry.log_path)
    return GenerateReportCommand(summary=summary).execute()


@app.get("/api/quarantine/{run_id}")
async def get_quarantine(run_id: str, fmt: str = "csv"):
    history = RunHistory()
    entry = history.get_run(run_id)
    if not entry:
        return JSONResponse({"error": "Run not found"}, status_code=404)

    reader = LogReader()
    summary = reader.read_summary(entry.log_path)
    path = ExportQuarantineCommand(
        summary=summary, output_dir=str(_OUTPUT_DIR), fmt=fmt
    ).execute()
    return {"path": path, "quarantined_count": summary.total_quarantined}


@app.get("/api/diff")
async def diff_runs(baseline_id: str, current_id: str):
    history = RunHistory()
    baseline_entry = history.get_run(baseline_id)
    current_entry = history.get_run(current_id)
    if not baseline_entry or not current_entry:
        return JSONResponse({"error": "Run(s) not found"}, status_code=404)

    reader = LogReader()
    baseline = reader.read_summary(baseline_entry.log_path)
    current = reader.read_summary(current_entry.log_path)
    diff = DiffService().compare(
        baseline, current,
        baseline_label=baseline_entry.run_id,
        current_label=current_entry.run_id,
    )
    html = GenerateDiffReportCommand(diff=diff).execute()
    return HTMLResponse(html)


@app.post("/api/validate")
async def validate_config(request: Request):
    try:
        body = await request.json()
        config = _build_config(body)
        return {"valid": True, "input_mode": config.input_mode.value,
                "output_mode": config.output_mode.value,
                "objects": list(config.objects)}
    except Exception as e:
        return JSONResponse({"valid": False, "error": str(e)}, status_code=400)


# ── Internal helpers ──

def _build_config(body: dict) -> MigrationConfig:
    input_mode = InputMode(body.get("input_mode", "csv"))
    output_mode = OutputMode(body.get("output_mode", "file"))

    sf = body.get("salesforce", {})
    sf_config = SalesforceApiConfig(
        username=sf.get("username", ""),
        password=sf.get("password", ""),
        security_token=sf.get("security_token", ""),
        domain=sf.get("domain", "login"),
    )

    csv_paths = body.get("csv_paths", {})
    csv_config = CsvConfig(
        accounts_path=csv_paths.get("accounts", ""),
        contacts_path=csv_paths.get("contacts", ""),
        opportunities_path=csv_paths.get("opportunities", ""),
        tasks_path=csv_paths.get("tasks", ""),
        events_path=csv_paths.get("events", ""),
    )

    nexus = body.get("nexus_api", {})
    nexus_config = NexusApiConfig(
        base_url=nexus.get("base_url", ""),
        api_key=nexus.get("api_key", ""),
        batch_size=nexus.get("batch_size", 50),
        dry_run=body.get("dry_run", False),
    )

    objects = tuple(body.get("objects", ["accounts", "contacts", "opportunities", "activities"]))
    dup = DuplicateStrategy(body.get("duplicate_strategy", "skip"))

    return MigrationConfig(
        input_mode=input_mode,
        output_mode=output_mode,
        salesforce=sf_config,
        csv=csv_config,
        nexus_api=nexus_config,
        file_export=FileExportConfig(output_dir=str(_OUTPUT_DIR), formats=("json", "csv")),
        objects=objects,
        duplicate_strategy=dup,
        field_overrides=body.get("field_overrides", {}),
        stage_overrides=body.get("stage_overrides", {}),
    )


async def _execute_migration(run_id: str, config: MigrationConfig,
                              progress: WebProgressAdapter, dry_run: bool):
    container = Container(config)
    try:
        command = RunMigrationCommand(
            config=config,
            extractor=container.extractor(),
            loader=container.loader(),
            file_exporter=container.file_exporter(),
            progress=progress,
        )
        summary = await command.execute()

        logger = MigrationLogger()
        log_path = logger.write_summary(summary)

        history = RunHistory()
        history.record(
            summary=summary,
            log_path=log_path,
            input_mode=config.input_mode.value,
            output_mode=config.output_mode.value,
            dry_run=dry_run,
        )

        # Override run_id to match what we returned to the client
        entries = history.list_runs(limit=1)
        if entries:
            import json as _json
            idx_path = Path("./logs") / "run_history.json"
            if idx_path.exists():
                data = _json.loads(idx_path.read_text())
                if data:
                    data[0]["run_id"] = run_id
                    idx_path.write_text(_json.dumps(data, indent=2))

        # Generate report
        report_html = GenerateReportCommand(summary=summary).execute()
        report_path = _OUTPUT_DIR / "migration_report.html"
        report_path.parent.mkdir(parents=True, exist_ok=True)
        report_path.write_text(report_html, encoding="utf-8")

        if summary.total_quarantined > 0:
            ExportQuarantineCommand(
                summary=summary, output_dir=str(_OUTPUT_DIR), fmt="csv"
            ).execute()

    finally:
        _run_complete[run_id] = True
        await container.cleanup()


def main():
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)


if __name__ == "__main__":
    main()
