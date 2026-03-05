"""
Remediation Service Tests -- Pure Domain Logic
"""
from domain.services.remediation_service import RemediationService
from domain.value_objects.migration_result import (
    BatchResult, MigrationSummary, RecordResult, RecordStatus,
)


def _summary_with_quarantined(messages: list[str], warnings: tuple[str, ...] = ()) -> MigrationSummary:
    results = tuple(
        RecordResult(salesforce_id=f"00{i}", object_type="Account",
                     status=RecordStatus.QUARANTINED, message=msg)
        for i, msg in enumerate(messages)
    )
    return MigrationSummary(
        batches=(BatchResult(
            object_type="Account", total=10, success_count=10 - len(messages),
            warning_count=0, error_count=0, quarantined_count=len(messages),
            record_results=results,
        ),),
        total_extracted=10, total_loaded=10 - len(messages),
        total_quarantined=len(messages), warnings=warnings,
    )


class TestRemediationService:
    def setup_method(self):
        self.service = RemediationService()

    def test_missing_required_field_recommendation(self):
        summary = _summary_with_quarantined([
            "Account 001: Name is required",
            "Account 002: Name is required",
        ])
        rems = self.service.analyse(summary)
        assert any("Missing required field" in r.pattern for r in rems)
        name_rem = next(r for r in rems if "Name" in r.pattern)
        assert name_rem.count == 2
        assert name_rem.severity == "critical"
        assert "field_override" in name_rem.recommendation

    def test_invalid_email_recommendation(self):
        results = (
            RecordResult(salesforce_id="003A", object_type="Contact",
                        status=RecordStatus.WARNING, message="Invalid email format: bad@"),
        )
        summary = MigrationSummary(
            batches=(BatchResult(
                object_type="Contact", total=5, success_count=5,
                warning_count=1, error_count=0, quarantined_count=0,
                record_results=results,
            ),),
            total_extracted=5, total_loaded=5,
        )
        rems = self.service.analyse(summary)
        assert any("email" in r.pattern.lower() for r in rems)

    def test_duplicate_recommendation(self):
        results = (
            RecordResult(salesforce_id="001B", object_type="Account",
                        status=RecordStatus.WARNING, message="Potential duplicate of 001A"),
        )
        summary = MigrationSummary(
            batches=(BatchResult(
                object_type="Account", total=5, success_count=5,
                warning_count=1, error_count=0, quarantined_count=0,
                record_results=results,
            ),),
            total_extracted=5, total_loaded=5,
        )
        rems = self.service.analyse(summary)
        assert any("duplicate" in r.pattern.lower() for r in rems)

    def test_unresolved_references(self):
        summary = _summary_with_quarantined(
            [], warnings=("Unresolved reference: 001ABC not found in lookup",)
        )
        rems = self.service.analyse(summary)
        assert any("Unresolved" in r.pattern for r in rems)

    def test_api_error_recommendation(self):
        results = (
            RecordResult(salesforce_id="001A", object_type="companies",
                        status=RecordStatus.ERROR, message="HTTP 429 after 3 retries"),
            RecordResult(salesforce_id="001B", object_type="companies",
                        status=RecordStatus.ERROR, message="HTTP 500 after 3 retries"),
        )
        summary = MigrationSummary(
            batches=(BatchResult(
                object_type="companies", total=10, success_count=8,
                warning_count=0, error_count=2, quarantined_count=0,
                record_results=results,
            ),),
            total_extracted=10, total_loaded=8,
        )
        rems = self.service.analyse(summary)
        assert any("API errors" in r.pattern for r in rems)

    def test_high_quarantine_rate(self):
        summary = _summary_with_quarantined(
            [f"Account {i}: Name is required" for i in range(6)]
        )
        # 6/10 = 60% quarantine rate
        rems = self.service.analyse(summary)
        assert any("quarantine rate" in r.pattern.lower() for r in rems)
        rate_rem = next(r for r in rems if "quarantine rate" in r.pattern.lower())
        assert rate_rem.severity == "critical"

    def test_clean_migration_no_remediations(self):
        results = tuple(
            RecordResult(salesforce_id=f"00{i}", object_type="Account",
                        status=RecordStatus.SUCCESS)
            for i in range(10)
        )
        summary = MigrationSummary(
            batches=(BatchResult(
                object_type="Account", total=10, success_count=10,
                warning_count=0, error_count=0, quarantined_count=0,
                record_results=results,
            ),),
            total_extracted=10, total_loaded=10,
        )
        rems = self.service.analyse(summary)
        assert rems == []

    def test_remediations_sorted_by_severity(self):
        results = (
            RecordResult(salesforce_id="001A", object_type="Account",
                        status=RecordStatus.QUARANTINED, message="Account 001A: Name is required"),
            RecordResult(salesforce_id="003A", object_type="Contact",
                        status=RecordStatus.WARNING, message="Potential duplicate of 003B"),
        )
        summary = MigrationSummary(
            batches=(BatchResult(
                object_type="Mixed", total=10, success_count=8,
                warning_count=1, error_count=0, quarantined_count=1,
                record_results=results,
            ),),
            total_extracted=10, total_loaded=9, total_quarantined=1,
        )
        rems = self.service.analyse(summary)
        severities = [r.severity for r in rems]
        assert severities == sorted(severities, key=lambda s: {"critical": 0, "warning": 1, "info": 2}[s])
