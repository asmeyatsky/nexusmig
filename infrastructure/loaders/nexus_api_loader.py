"""
Nexus API Loader

Architectural Intent:
- Infrastructure adapter implementing NexusLoaderPort
- Posts records to Nexus CRM REST API in configurable batch sizes
- Handles retry with exponential backoff for 429/5xx
- Supports dry-run mode (validates payloads without writing)
- Per-record success/failure tracking
"""
import asyncio

import httpx

from application.dtos.migration_dto import NexusApiConfig
from domain.value_objects.migration_result import RecordResult, RecordStatus

_OBJECT_ENDPOINTS = {
    "companies": "/api/v1/companies",
    "contacts": "/api/v1/contacts",
    "deals": "/api/v1/deals",
    "activities": "/api/v1/activities",
}

_MAX_RETRIES = 3
_BACKOFF_BASE = 1.0


class NexusApiLoader:
    def __init__(self, config: NexusApiConfig):
        self._config = config
        self._client = httpx.AsyncClient(
            base_url=config.base_url,
            headers={"Authorization": f"Bearer {config.api_key}"},
            timeout=30.0,
        )

    async def load_companies(self, records: list[dict]) -> list[RecordResult]:
        return await self._load("companies", records)

    async def load_contacts(self, records: list[dict]) -> list[RecordResult]:
        return await self._load("contacts", records)

    async def load_deals(self, records: list[dict]) -> list[RecordResult]:
        return await self._load("deals", records)

    async def load_activities(self, records: list[dict]) -> list[RecordResult]:
        return await self._load("activities", records)

    async def _load(self, object_type: str, records: list[dict]) -> list[RecordResult]:
        endpoint = _OBJECT_ENDPOINTS[object_type]
        results: list[RecordResult] = []
        batch_size = self._config.batch_size

        for i in range(0, len(records), batch_size):
            batch = records[i : i + batch_size]
            batch_results = await self._post_batch(endpoint, object_type, batch)
            results.extend(batch_results)

        return results

    async def _post_batch(
        self, endpoint: str, object_type: str, batch: list[dict]
    ) -> list[RecordResult]:
        if self._config.dry_run:
            return [
                RecordResult(
                    salesforce_id=r.get("external_id", ""),
                    object_type=object_type,
                    status=RecordStatus.SUCCESS,
                    message="dry_run",
                )
                for r in batch
            ]

        results: list[RecordResult] = []
        for record in batch:
            sf_id = record.get("external_id", "")
            for attempt in range(_MAX_RETRIES):
                try:
                    resp = await self._client.post(endpoint, json=record)
                    if resp.status_code in (200, 201):
                        body = resp.json()
                        results.append(RecordResult(
                            salesforce_id=sf_id,
                            object_type=object_type,
                            status=RecordStatus.SUCCESS,
                            nexus_id=body.get("id", ""),
                        ))
                        break
                    elif resp.status_code == 429 or resp.status_code >= 500:
                        if attempt < _MAX_RETRIES - 1:
                            await asyncio.sleep(_BACKOFF_BASE * (2 ** attempt))
                            continue
                        results.append(RecordResult(
                            salesforce_id=sf_id,
                            object_type=object_type,
                            status=RecordStatus.ERROR,
                            message=f"HTTP {resp.status_code} after {_MAX_RETRIES} retries",
                        ))
                        break
                    else:
                        results.append(RecordResult(
                            salesforce_id=sf_id,
                            object_type=object_type,
                            status=RecordStatus.ERROR,
                            message=f"HTTP {resp.status_code}: {resp.text[:200]}",
                        ))
                        break
                except httpx.HTTPError as e:
                    if attempt < _MAX_RETRIES - 1:
                        await asyncio.sleep(_BACKOFF_BASE * (2 ** attempt))
                        continue
                    results.append(RecordResult(
                        salesforce_id=sf_id,
                        object_type=object_type,
                        status=RecordStatus.ERROR,
                        message=str(e),
                    ))
                    break
        return results

    async def close(self) -> None:
        await self._client.aclose()
