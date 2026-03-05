"""
CSV Extractor Integration Tests
"""
import pytest
import tempfile
from pathlib import Path

from application.dtos.migration_dto import CsvConfig
from infrastructure.extractors.csv_extractor import CsvExtractor


@pytest.fixture
def csv_dir():
    with tempfile.TemporaryDirectory() as d:
        yield Path(d)


def _write_csv(path: Path, content: str):
    path.write_text(content, encoding="utf-8")


class TestCsvExtractor:
    @pytest.mark.asyncio
    async def test_extract_accounts(self, csv_dir):
        csv_path = csv_dir / "accounts.csv"
        _write_csv(csv_path, "Id,Name,Industry\n001,Acme,Tech\n002,Beta,Finance\n")

        extractor = CsvExtractor(CsvConfig(accounts_path=str(csv_path)))
        records = await extractor.extract_accounts()

        assert len(records) == 2
        assert records[0]["Id"] == "001"
        assert records[0]["Name"] == "Acme"

    @pytest.mark.asyncio
    async def test_missing_required_header_raises(self, csv_dir):
        csv_path = csv_dir / "accounts.csv"
        _write_csv(csv_path, "Industry,Website\nTech,acme.com\n")

        extractor = CsvExtractor(CsvConfig(accounts_path=str(csv_path)))
        with pytest.raises(ValueError, match="missing required columns"):
            await extractor.extract_accounts()

    @pytest.mark.asyncio
    async def test_file_not_found_raises(self):
        extractor = CsvExtractor(CsvConfig(accounts_path="/nonexistent/path.csv"))
        with pytest.raises(FileNotFoundError):
            await extractor.extract_accounts()

    @pytest.mark.asyncio
    async def test_empty_path_returns_empty_list(self):
        extractor = CsvExtractor(CsvConfig())
        result = await extractor.extract_accounts()
        assert result == []

    @pytest.mark.asyncio
    async def test_utf8_bom_handling(self, csv_dir):
        csv_path = csv_dir / "contacts.csv"
        # Write with BOM
        csv_path.write_bytes(b"\xef\xbb\xbfId,LastName\n003,M\xc3\xbcller\n")

        extractor = CsvExtractor(CsvConfig(contacts_path=str(csv_path)))
        records = await extractor.extract_contacts()

        assert len(records) == 1
        assert records[0]["LastName"] == "Müller"
