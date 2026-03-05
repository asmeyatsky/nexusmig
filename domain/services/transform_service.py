"""
Transform Domain Service

Architectural Intent:
- Pure domain logic for data cleaning and normalisation
- No infrastructure dependencies — operates only on domain entities
- Handles: null detection, encoding cleanup, date/URL/email normalisation, duplicate detection

Parallelization Notes:
- Per-record transforms are independent and can be parallelized at the orchestration layer
- Duplicate detection requires the full set and must run after individual transforms
"""
import re
from dataclasses import replace
from datetime import datetime, UTC
from urllib.parse import urlparse

from domain.entities.account import Account
from domain.entities.contact import Contact
from domain.entities.opportunity import Opportunity
from domain.entities.activity import Activity
from domain.value_objects.migration_result import RecordResult, RecordStatus


_EMAIL_RE = re.compile(r"^[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}$")


class TransformService:
    def transform_account(self, account: Account) -> tuple[Account, list[RecordResult]]:
        warnings: list[RecordResult] = []
        transformed = replace(
            account,
            name=self._clean_string(account.name),
            website=self._normalise_url(account.website),
            phone=self._clean_string(account.phone),
            description=self._clean_string(account.description),
            billing_street=self._clean_string(account.billing_street),
            billing_city=self._clean_string(account.billing_city),
            billing_state=self._clean_string(account.billing_state),
            billing_postal_code=self._clean_string(account.billing_postal_code),
            billing_country=self._clean_string(account.billing_country),
            created_date=self._normalise_date(account.created_date),
        )
        return transformed, warnings

    def transform_contact(self, contact: Contact) -> tuple[Contact, list[RecordResult]]:
        warnings: list[RecordResult] = []
        email = contact.email.lower().strip() if contact.email else ""
        if email and not _EMAIL_RE.match(email):
            warnings.append(RecordResult(
                salesforce_id=contact.sf_id,
                object_type="Contact",
                status=RecordStatus.WARNING,
                message=f"Invalid email format: {email}",
            ))
        transformed = replace(
            contact,
            first_name=self._clean_string(contact.first_name),
            last_name=self._clean_string(contact.last_name),
            email=email,
            phone=self._clean_string(contact.phone),
            title=self._clean_string(contact.title),
            description=self._clean_string(contact.description),
            created_date=self._normalise_date(contact.created_date),
        )
        return transformed, warnings

    def transform_opportunity(self, opp: Opportunity) -> tuple[Opportunity, list[RecordResult]]:
        warnings: list[RecordResult] = []
        transformed = replace(
            opp,
            name=self._clean_string(opp.name),
            description=self._clean_string(opp.description),
            close_date=self._normalise_date(opp.close_date),
            created_date=self._normalise_date(opp.created_date),
        )
        return transformed, warnings

    def transform_activity(self, activity: Activity) -> tuple[Activity, list[RecordResult]]:
        warnings: list[RecordResult] = []
        transformed = replace(
            activity,
            subject=self._clean_string(activity.subject),
            description=self._clean_string(activity.description),
            activity_date=self._normalise_date(activity.activity_date),
            due_date=self._normalise_date(activity.due_date),
            created_date=self._normalise_date(activity.created_date),
        )
        return transformed, warnings

    def detect_duplicate_accounts(self, accounts: list[Account]) -> list[RecordResult]:
        return self._detect_duplicates(
            [(a.sf_id, a.name.strip().lower()) for a in accounts], "Account"
        )

    def detect_duplicate_contacts(self, contacts: list[Contact]) -> list[RecordResult]:
        return self._detect_duplicates(
            [(c.sf_id, c.email.lower().strip()) for c in contacts if c.email], "Contact"
        )

    def _detect_duplicates(
        self, id_key_pairs: list[tuple[str, str]], object_type: str
    ) -> list[RecordResult]:
        seen: dict[str, str] = {}
        warnings: list[RecordResult] = []
        for sf_id, key in id_key_pairs:
            if key in seen:
                warnings.append(RecordResult(
                    salesforce_id=sf_id,
                    object_type=object_type,
                    status=RecordStatus.WARNING,
                    message=f"Potential duplicate of {seen[key]} (key: {key})",
                ))
            else:
                seen[key] = sf_id
        return warnings

    @staticmethod
    def _clean_string(value: str) -> str:
        if not value:
            return ""
        cleaned = value.encode("utf-8", errors="replace").decode("utf-8")
        return cleaned.strip()

    @staticmethod
    def _normalise_url(url: str) -> str:
        if not url:
            return ""
        url = url.strip()
        if not url:
            return ""
        parsed = urlparse(url)
        if not parsed.scheme:
            url = f"https://{url}"
        return url

    @staticmethod
    def _normalise_date(date_str: str) -> str:
        if not date_str:
            return ""
        date_str = date_str.strip()
        for fmt in ("%Y-%m-%dT%H:%M:%S.%f%z", "%Y-%m-%dT%H:%M:%S%z",
                     "%Y-%m-%dT%H:%M:%S", "%Y-%m-%d", "%m/%d/%Y", "%d/%m/%Y"):
            try:
                dt = datetime.strptime(date_str, fmt)
                if dt.tzinfo is None:
                    dt = dt.replace(tzinfo=UTC)
                return dt.isoformat()
            except ValueError:
                continue
        return date_str
