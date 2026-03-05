"""
Web API Tests

Tests the FastAPI endpoints using httpx TestClient.
"""
import io
import json
import pytest
import tempfile
from pathlib import Path
from unittest.mock import patch

from fastapi.testclient import TestClient

from presentation.web.app import app


@pytest.fixture
def client():
    return TestClient(app)


class TestWebPages:
    def test_index_page_loads(self, client):
        resp = client.get("/")
        assert resp.status_code == 200
        assert "Nexus Migration Accelerator" in resp.text

    def test_static_css_loads(self, client):
        resp = client.get("/static/style.css")
        assert resp.status_code == 200

    def test_static_js_loads(self, client):
        resp = client.get("/static/app.js")
        assert resp.status_code == 200


class TestUploadAPI:
    def test_upload_csv_files(self, client):
        accounts_csv = io.BytesIO(b"Id,Name\n001,Acme\n")
        resp = client.post("/api/upload-csv", files={
            "accounts": ("accounts.csv", accounts_csv, "text/csv"),
        })
        assert resp.status_code == 200
        data = resp.json()
        assert "session_id" in data
        assert "accounts" in data["uploaded"]
        assert "accounts" in data["paths"]

    def test_upload_multiple_files(self, client):
        resp = client.post("/api/upload-csv", files={
            "accounts": ("accounts.csv", io.BytesIO(b"Id,Name\n001,A\n"), "text/csv"),
            "contacts": ("contacts.csv", io.BytesIO(b"Id,LastName\n003,D\n"), "text/csv"),
        })
        data = resp.json()
        assert len(data["uploaded"]) == 2


class TestValidateAPI:
    def test_validate_valid_config(self, client):
        resp = client.post("/api/validate", json={
            "input_mode": "csv",
            "output_mode": "file",
            "objects": ["accounts"],
        })
        assert resp.status_code == 200
        assert resp.json()["valid"] is True

    def test_validate_invalid_mode(self, client):
        resp = client.post("/api/validate", json={
            "input_mode": "invalid_mode",
        })
        assert resp.status_code == 400
        assert resp.json()["valid"] is False


class TestHistoryAPI:
    def test_get_history_empty(self, client):
        with tempfile.TemporaryDirectory() as tmpdir:
            with patch("presentation.web.app.RunHistory") as MockHistory:
                MockHistory.return_value.list_runs.return_value = []
                resp = client.get("/api/history")
                assert resp.status_code == 200
                assert isinstance(resp.json(), list)


class TestRunAPI:
    def test_start_run_returns_run_id(self, client):
        # Upload a CSV first
        resp = client.post("/api/upload-csv", files={
            "accounts": ("accounts.csv", io.BytesIO(b"Id,Name\n001,Acme\n"), "text/csv"),
        })
        paths = resp.json()["paths"]

        # Start a run
        resp = client.post("/api/run", json={
            "input_mode": "csv",
            "output_mode": "file",
            "objects": ["accounts"],
            "csv_paths": paths,
            "dry_run": True,
        })
        assert resp.status_code == 200
        assert "run_id" in resp.json()
