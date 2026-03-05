"""
CSV Extractor

Architectural Intent:
- Infrastructure adapter implementing SalesforceExtractorPort for CSV input mode
- Reads manually exported Salesforce CSV files
- Validates headers against expected column names
- No business logic — pure file I/O and parsing
"""
import asyncio
import csv
from pathlib import Path

from application.dtos.migration_dto import CsvConfig

_REQUIRED_HEADERS: dict[str, list[str]] = {
    "accounts": ["Id", "Name"],
    "contacts": ["Id", "LastName"],
    "opportunities": ["Id", "Name"],
    "tasks": ["Id", "Subject"],
    "events": ["Id", "Subject"],
}


class CsvExtractor:
    def __init__(self, config: CsvConfig):
        self._config = config

    async def extract_accounts(self) -> list[dict]:
        return await self._read_csv(self._config.accounts_path, "accounts")

    async def extract_contacts(self) -> list[dict]:
        return await self._read_csv(self._config.contacts_path, "contacts")

    async def extract_opportunities(self) -> list[dict]:
        return await self._read_csv(self._config.opportunities_path, "opportunities")

    async def extract_tasks(self) -> list[dict]:
        return await self._read_csv(self._config.tasks_path, "tasks")

    async def extract_events(self) -> list[dict]:
        return await self._read_csv(self._config.events_path, "events")

    async def _read_csv(self, path: str, object_type: str) -> list[dict]:
        if not path:
            return []
        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(None, self._read_csv_sync, path, object_type)

    def _read_csv_sync(self, path: str, object_type: str) -> list[dict]:
        file_path = Path(path)
        if not file_path.exists():
            raise FileNotFoundError(f"CSV file not found: {path}")

        with open(file_path, "r", encoding="utf-8-sig") as f:
            reader = csv.DictReader(f)
            headers = reader.fieldnames or []
            self._validate_headers(headers, object_type)
            return [self._normalise_row(row) for row in reader]

    @staticmethod
    def _validate_headers(headers: list[str], object_type: str) -> None:
        required = _REQUIRED_HEADERS.get(object_type, [])
        missing = [h for h in required if h not in headers]
        if missing:
            raise ValueError(
                f"CSV for {object_type} is missing required columns: {', '.join(missing)}"
            )

    @staticmethod
    def _normalise_row(row: dict) -> dict:
        return {k: (v if v else "") for k, v in row.items()}
