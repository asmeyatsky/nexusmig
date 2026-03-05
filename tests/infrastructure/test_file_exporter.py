"""
File Exporter Integration Tests
"""
import json
import csv
import pytest
import tempfile
from pathlib import Path

from infrastructure.loaders.file_exporter import FileExporter


@pytest.fixture
def output_dir():
    with tempfile.TemporaryDirectory() as d:
        yield d


class TestFileExporter:
    @pytest.mark.asyncio
    async def test_export_json(self, output_dir):
        exporter = FileExporter(output_dir)
        records = [{"name": "Acme", "external_id": "001"}, {"name": "Beta", "external_id": "002"}]

        path = await exporter.export("companies", records, "json")

        assert Path(path).exists()
        data = json.loads(Path(path).read_text())
        assert len(data) == 2
        assert data[0]["name"] == "Acme"

    @pytest.mark.asyncio
    async def test_export_csv(self, output_dir):
        exporter = FileExporter(output_dir)
        records = [{"name": "Acme", "industry": "Tech"}, {"name": "Beta", "industry": "Finance"}]

        path = await exporter.export("companies", records, "csv")

        assert Path(path).exists()
        with open(path) as f:
            reader = list(csv.DictReader(f))
        assert len(reader) == 2
        assert reader[0]["name"] == "Acme"

    @pytest.mark.asyncio
    async def test_export_csv_flattens_nested_dicts(self, output_dir):
        exporter = FileExporter(output_dir)
        records = [{"name": "Acme", "address": {"street": "123 Main", "city": "Springfield"}}]

        path = await exporter.export("companies", records, "csv")

        with open(path) as f:
            reader = list(csv.DictReader(f))
        assert reader[0]["address_street"] == "123 Main"
        assert reader[0]["address_city"] == "Springfield"

    @pytest.mark.asyncio
    async def test_export_empty_records(self, output_dir):
        exporter = FileExporter(output_dir)
        path = await exporter.export("companies", [], "csv")
        assert Path(path).exists()

    @pytest.mark.asyncio
    async def test_unsupported_format_raises(self, output_dir):
        exporter = FileExporter(output_dir)
        with pytest.raises(ValueError, match="Unsupported export format"):
            await exporter.export("companies", [], "xml")
