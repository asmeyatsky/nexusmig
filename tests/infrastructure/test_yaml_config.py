"""
YAML Config Loader Tests
"""
import pytest
import tempfile
from pathlib import Path

from application.dtos.migration_dto import InputMode, OutputMode
from infrastructure.config.yaml_config import load_config


@pytest.fixture
def config_file():
    content = """
input_mode: csv
output_mode: both
csv:
  accounts: ./data/accounts.csv
  contacts: ./data/contacts.csv
nexus_api:
  base_url: https://api.nexus.test
  api_key: test-key-123
  batch_size: 25
  dry_run: true
file_export:
  output_dir: ./test_output
  formats:
    - json
    - csv
objects:
  - accounts
  - contacts
duplicate_strategy: keep_both
field_overrides:
  Account:
    Custom_Name__c: Name
"""
    with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
        f.write(content)
        return f.name


class TestYamlConfig:
    def test_loads_valid_config(self, config_file):
        config = load_config(config_file)
        assert config.input_mode == InputMode.CSV
        assert config.output_mode == OutputMode.BOTH
        assert config.nexus_api.base_url == "https://api.nexus.test"
        assert config.nexus_api.batch_size == 25
        assert config.nexus_api.dry_run is True
        assert config.objects == ("accounts", "contacts")
        assert "Account" in config.field_overrides

    def test_file_not_found_raises(self):
        with pytest.raises(FileNotFoundError):
            load_config("/nonexistent/config.yaml")
