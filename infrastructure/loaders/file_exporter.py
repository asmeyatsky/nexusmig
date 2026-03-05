"""
File Exporter

Architectural Intent:
- Infrastructure adapter implementing FileExporterPort
- Exports transformed records to JSON or CSV files
- Returns output file path for audit trail
"""
import asyncio
import csv
import json
from pathlib import Path


class FileExporter:
    def __init__(self, output_dir: str):
        self._output_dir = Path(output_dir)
        self._output_dir.mkdir(parents=True, exist_ok=True)

    async def export(self, object_type: str, records: list[dict], fmt: str) -> str:
        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(
            None, self._export_sync, object_type, records, fmt
        )

    def _export_sync(self, object_type: str, records: list[dict], fmt: str) -> str:
        if fmt == "json":
            return self._export_json(object_type, records)
        elif fmt == "csv":
            return self._export_csv(object_type, records)
        else:
            raise ValueError(f"Unsupported export format: {fmt}")

    def _export_json(self, object_type: str, records: list[dict]) -> str:
        path = self._output_dir / f"{object_type}.json"
        with open(path, "w", encoding="utf-8") as f:
            json.dump(records, f, indent=2, ensure_ascii=False, default=str)
        return str(path)

    def _export_csv(self, object_type: str, records: list[dict]) -> str:
        if not records:
            path = self._output_dir / f"{object_type}.csv"
            path.touch()
            return str(path)

        # Flatten nested dicts for CSV (e.g. address.street -> address_street)
        flat_records = [self._flatten(r) for r in records]
        all_keys: list[str] = []
        seen: set[str] = set()
        for rec in flat_records:
            for k in rec:
                if k not in seen:
                    all_keys.append(k)
                    seen.add(k)

        path = self._output_dir / f"{object_type}.csv"
        with open(path, "w", encoding="utf-8", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=all_keys)
            writer.writeheader()
            writer.writerows(flat_records)
        return str(path)

    @staticmethod
    def _flatten(d: dict, parent_key: str = "", sep: str = "_") -> dict:
        items: list[tuple[str, object]] = []
        for k, v in d.items():
            new_key = f"{parent_key}{sep}{k}" if parent_key else k
            if isinstance(v, dict):
                items.extend(FileExporter._flatten(v, new_key, sep).items())
            else:
                items.append((new_key, v))
        return dict(items)
