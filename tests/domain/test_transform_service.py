"""
Transform Service Tests — Pure Domain Logic, No Mocks
"""
from domain.entities.account import Account
from domain.entities.contact import Contact
from domain.services.transform_service import TransformService
from domain.value_objects.migration_result import RecordStatus


class TestTransformService:
    def setup_method(self):
        self.service = TransformService()

    def test_clean_string_strips_whitespace(self):
        assert TransformService._clean_string("  hello  ") == "hello"

    def test_clean_string_handles_empty(self):
        assert TransformService._clean_string("") == ""

    def test_normalise_url_adds_https(self):
        assert TransformService._normalise_url("example.com") == "https://example.com"

    def test_normalise_url_preserves_existing_scheme(self):
        assert TransformService._normalise_url("https://example.com") == "https://example.com"

    def test_normalise_url_empty(self):
        assert TransformService._normalise_url("") == ""

    def test_normalise_date_iso_format(self):
        result = TransformService._normalise_date("2024-01-15")
        assert "2024-01-15" in result

    def test_normalise_date_us_format(self):
        result = TransformService._normalise_date("01/15/2024")
        assert "2024" in result

    def test_normalise_date_sf_datetime(self):
        result = TransformService._normalise_date("2024-01-15T10:30:00.000+0000")
        assert "2024-01-15" in result

    def test_normalise_date_empty(self):
        assert TransformService._normalise_date("") == ""

    def test_transform_account_cleans_fields(self):
        account = Account(sf_id="001", name="  Acme Corp  ", website="acme.com")
        transformed, warnings = self.service.transform_account(account)
        assert transformed.name == "Acme Corp"
        assert transformed.website == "https://acme.com"

    def test_transform_contact_lowercases_email(self):
        contact = Contact(sf_id="003", last_name="Doe", email="  JOHN@TEST.COM  ")
        transformed, warnings = self.service.transform_contact(contact)
        assert transformed.email == "john@test.com"

    def test_transform_contact_flags_invalid_email(self):
        contact = Contact(sf_id="003", last_name="Doe", email="not-an-email")
        _, warnings = self.service.transform_contact(contact)
        assert len(warnings) == 1
        assert warnings[0].status == RecordStatus.WARNING

    def test_detect_duplicate_accounts(self):
        accounts = [
            Account(sf_id="001", name="Acme Corp"),
            Account(sf_id="002", name="acme corp"),
            Account(sf_id="003", name="Other Inc"),
        ]
        warnings = self.service.detect_duplicate_accounts(accounts)
        assert len(warnings) == 1
        assert "002" in warnings[0].salesforce_id

    def test_detect_duplicate_contacts_by_email(self):
        contacts = [
            Contact(sf_id="003A", last_name="Doe", email="john@test.com"),
            Contact(sf_id="003B", last_name="Smith", email="john@test.com"),
        ]
        warnings = self.service.detect_duplicate_contacts(contacts)
        assert len(warnings) == 1

    def test_no_duplicates_when_unique(self):
        accounts = [
            Account(sf_id="001", name="Alpha"),
            Account(sf_id="002", name="Beta"),
        ]
        assert self.service.detect_duplicate_accounts(accounts) == []
