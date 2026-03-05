"""
Progress Port

Architectural Intent:
- Observer-pattern port for streaming migration progress
- Domain/application layer emits progress events
- Infrastructure/presentation layer consumes them (CLI, MCP, web UI)
"""
from dataclasses import dataclass
from typing import Protocol


@dataclass(frozen=True)
class ProgressEvent:
    phase: str  # "extract", "transform", "load", "complete"
    object_type: str
    current: int
    total: int
    message: str = ""


class ProgressPort(Protocol):
    def on_progress(self, event: ProgressEvent) -> None: ...
