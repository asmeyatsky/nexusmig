"""
Value Object Tests
"""
import pytest
from domain.value_objects.salesforce_id import SalesforceId
from domain.value_objects.errors import DomainError
from domain.value_objects.migration_result import RecordResult, RecordStatus, BatchResult


class TestSalesforceId:
    def test_valid_15_char_id(self):
        sf_id = SalesforceId("001000000000ABC")
        assert sf_id.value == "001000000000ABC"

    def test_valid_18_char_id(self):
        sf_id = SalesforceId("001000000000ABCdef")
        assert sf_id.value == "001000000000ABCdef"

    def test_invalid_length_raises(self):
        with pytest.raises(DomainError, match="Invalid Salesforce ID"):
            SalesforceId("short")

    def test_empty_raises(self):
        with pytest.raises(DomainError):
            SalesforceId("")


class TestRecordResult:
    def test_immutable(self):
        result = RecordResult(salesforce_id="001", object_type="Account", status=RecordStatus.SUCCESS)
        with pytest.raises(AttributeError):
            result.status = RecordStatus.ERROR

    def test_batch_result(self):
        batch = BatchResult(
            object_type="Account", total=10, success_count=8,
            warning_count=1, error_count=0, quarantined_count=1,
        )
        assert batch.total == 10
        assert batch.success_count == 8
