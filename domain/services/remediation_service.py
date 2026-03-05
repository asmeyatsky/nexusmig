"""
Remediation Recommendation Service

Architectural Intent:
- Pure domain logic that analyses migration results and produces
  actionable remediation recommendations grouped by error pattern
- No infrastructure dependencies
- Consumed by the report generator to populate the remediation section
"""
import re
from collections import Counter
from dataclasses import dataclass

from domain.value_objects.migration_result import MigrationSummary, RecordStatus


@dataclass(frozen=True)
class Remediation:
    pattern: str
    count: int
    severity: str  # "critical", "warning", "info"
    recommendation: str
    affected_ids: tuple[str, ...] = ()


class RemediationService:
    def analyse(self, summary: MigrationSummary) -> list[Remediation]:
        all_results = []
        for batch in summary.batches:
            all_results.extend(batch.record_results)

        remediations: list[Remediation] = []

        remediations.extend(self._check_missing_required_fields(all_results))
        remediations.extend(self._check_invalid_emails(all_results))
        remediations.extend(self._check_duplicates(all_results))
        remediations.extend(self._check_unresolved_references(summary.warnings))
        remediations.extend(self._check_api_errors(all_results))
        remediations.extend(self._check_quarantine_rate(summary))

        return sorted(remediations, key=lambda r: {"critical": 0, "warning": 1, "info": 2}[r.severity])

    def _check_missing_required_fields(self, results) -> list[Remediation]:
        pattern_re = re.compile(r"(\w+) .+: (\w+) is required")
        by_field: dict[str, list[str]] = {}
        for r in results:
            if r.status != RecordStatus.QUARANTINED:
                continue
            match = pattern_re.search(r.message)
            if match:
                key = f"{match.group(1)}.{match.group(2)}"
                by_field.setdefault(key, []).append(r.salesforce_id)

        remediations = []
        for field_key, ids in by_field.items():
            obj, field = field_key.split(".", 1)
            remediations.append(Remediation(
                pattern=f"Missing required field: {field_key}",
                count=len(ids),
                severity="critical",
                recommendation=(
                    f"{len(ids)} {obj} record(s) quarantined due to missing '{field}'. "
                    f"Options: (1) Populate '{field}' in Salesforce and re-export, "
                    f"(2) Add a field_override in migration.yaml mapping a custom field "
                    f"to '{field}', or (3) Set a default value in a pre-processing step."
                ),
                affected_ids=tuple(ids[:20]),
            ))
        return remediations

    def _check_invalid_emails(self, results) -> list[Remediation]:
        ids = [r.salesforce_id for r in results
               if r.status == RecordStatus.WARNING and "email format" in r.message.lower()]
        if not ids:
            return []
        return [Remediation(
            pattern="Invalid email format",
            count=len(ids),
            severity="warning",
            recommendation=(
                f"{len(ids)} contact(s) have invalid email addresses. "
                "These records were migrated but the email field may not "
                "match Nexus validation rules. Review and correct in Salesforce "
                "before re-running, or clean up in Nexus post-migration."
            ),
            affected_ids=tuple(ids[:20]),
        )]

    def _check_duplicates(self, results) -> list[Remediation]:
        ids = [r.salesforce_id for r in results
               if r.status == RecordStatus.WARNING and "duplicate" in r.message.lower()]
        if not ids:
            return []
        return [Remediation(
            pattern="Potential duplicates detected",
            count=len(ids),
            severity="warning",
            recommendation=(
                f"{len(ids)} potential duplicate(s) found. Current strategy: "
                "configured in migration.yaml (skip/overwrite/keep_both). "
                "Review flagged records and consider deduplicating in Salesforce "
                "before migration, or merge in Nexus post-migration."
            ),
            affected_ids=tuple(ids[:20]),
        )]

    def _check_unresolved_references(self, warnings: tuple[str, ...]) -> list[Remediation]:
        unresolved = [w for w in warnings if "Unresolved reference" in w]
        if not unresolved:
            return []

        by_context: dict[str, int] = Counter()
        for w in unresolved:
            if "->" in w:
                by_context["cross-object"] += 1
            else:
                by_context["unknown"] += 1

        return [Remediation(
            pattern="Unresolved cross-object references",
            count=len(unresolved),
            severity="warning",
            recommendation=(
                f"{len(unresolved)} reference(s) could not be resolved. This typically "
                "means a Contact references an Account, or an Activity references an "
                "Opportunity, that was not included in the migration scope. "
                "Ensure all related parent objects are included in the 'objects' config, "
                "or accept that these relationships will be unlinked in Nexus."
            ),
        )]

    def _check_api_errors(self, results) -> list[Remediation]:
        errors = [r for r in results if r.status == RecordStatus.ERROR]
        if not errors:
            return []

        http_errors = [r for r in errors if "HTTP" in r.message]
        other_errors = [r for r in errors if "HTTP" not in r.message]

        remediations = []
        if http_errors:
            status_counts: dict[str, int] = Counter()
            for r in http_errors:
                code_match = re.search(r"HTTP (\d+)", r.message)
                if code_match:
                    status_counts[code_match.group(1)] += 1

            details = ", ".join(f"{code}: {cnt}x" for code, cnt in status_counts.items())
            remediations.append(Remediation(
                pattern="Nexus API errors",
                count=len(http_errors),
                severity="critical",
                recommendation=(
                    f"{len(http_errors)} record(s) failed to load via Nexus API ({details}). "
                    "For 429 errors: reduce batch_size in migration.yaml. "
                    "For 5xx errors: check Nexus API health and retry. "
                    "For 4xx errors: inspect the quarantine log for payload issues. "
                    "Consider re-running with --dry-run to validate payloads first."
                ),
                affected_ids=tuple(r.salesforce_id for r in http_errors[:20]),
            ))

        if other_errors:
            remediations.append(Remediation(
                pattern="Non-HTTP load errors",
                count=len(other_errors),
                severity="critical",
                recommendation=(
                    f"{len(other_errors)} record(s) failed with non-HTTP errors "
                    "(network timeout, connection refused, etc). "
                    "Verify Nexus API base_url and network connectivity, then retry."
                ),
                affected_ids=tuple(r.salesforce_id for r in other_errors[:20]),
            ))

        return remediations

    def _check_quarantine_rate(self, summary: MigrationSummary) -> list[Remediation]:
        if summary.total_extracted == 0:
            return []
        rate = summary.total_quarantined / summary.total_extracted
        if rate < 0.05:
            return []
        return [Remediation(
            pattern="High quarantine rate",
            count=summary.total_quarantined,
            severity="critical" if rate > 0.20 else "warning",
            recommendation=(
                f"{summary.total_quarantined}/{summary.total_extracted} records quarantined "
                f"({rate:.0%}). This suggests systematic data quality issues in the "
                "Salesforce org. Run a data quality audit on required fields before "
                "re-attempting migration. Consider using field_overrides to map "
                "non-standard field names."
            ),
        )]
