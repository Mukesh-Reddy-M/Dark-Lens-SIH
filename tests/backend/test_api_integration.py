"""Automated Backend API and Import Integration Test Suite for DarkLens (SIH 2026).

Tests all 12 API routes (success, invalid input, missing fields, 404/409/422 status codes),
verifies test_cases/ bundle validation, and checks DB reset determinism.
Uses standard library unittest and asyncio ASGI client with zero external dependencies.
"""

from __future__ import annotations

import asyncio
import json
import os
import sqlite3
import unittest
import urllib.parse
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
TEST_DB = ROOT / "tmp" / "test_api_integration.sqlite3"

import sys
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

# Configure database path for backend before importing app
os.environ["DARKLENS_DB_PATH"] = str(TEST_DB)

from backend.app.database import init_db, seed_nightjar, session
from backend.app.main import app


class ASGIResponse:
    def __init__(self, status_code: int, headers: dict[str, str], body: bytes):
        self.status_code = status_code
        self.headers = headers
        self.content = body
        self.text = body.decode("utf-8", errors="replace")

    def json(self) -> Any:
        return json.loads(self.text)


class ASGIClient:
    def __init__(self, asgi_app):
        self.app = asgi_app

    def request(
        self,
        method: str,
        path: str,
        params: dict[str, Any] | None = None,
        json_data: Any = None,
        data: bytes | None = None,
        headers: dict[str, str] | None = None,
    ) -> ASGIResponse:
        req_headers = {"accept": "application/json"}
        if headers:
            for k, v in headers.items():
                req_headers[k.lower()] = v

        body_bytes = b""
        if json_data is not None:
            body_bytes = json.dumps(json_data).encode("utf-8")
            if "content-type" not in req_headers:
                req_headers["content-type"] = "application/json"
        elif data is not None:
            body_bytes = data
            if "content-type" not in req_headers:
                req_headers["content-type"] = "application/json"

        parsed = urllib.parse.urlparse(path)
        actual_path = parsed.path
        query_dict = dict(urllib.parse.parse_qsl(parsed.query))
        if params:
            query_dict.update(params)
        query_string = urllib.parse.urlencode(query_dict).encode("utf-8")

        raw_headers = [
            (k.encode("utf-8"), v.encode("utf-8"))
            for k, v in req_headers.items()
        ]

        scope = {
            "type": "http",
            "asgi": {"version": "3.0"},
            "http_version": "1.1",
            "method": method.upper(),
            "path": actual_path,
            "raw_path": actual_path.encode("utf-8"),
            "query_string": query_string,
            "headers": raw_headers,
            "server": ("127.0.0.1", 8001),
        }

        response_status = 200
        response_headers: dict[str, str] = {}
        response_body = bytearray()

        sent_body = False

        async def receive():
            nonlocal sent_body
            if not sent_body:
                sent_body = True
                return {"type": "http.request", "body": body_bytes, "more_body": False}
            return {"type": "http.request", "body": b"", "more_body": False}

        async def send(message):
            nonlocal response_status, response_headers, response_body
            if message["type"] == "http.response.start":
                response_status = message["status"]
                for k, v in message.get("headers", []):
                    response_headers[k.decode("utf-8").lower()] = v.decode("utf-8")
            elif message["type"] == "http.response.body":
                response_body.extend(message.get("body", b""))

        asyncio.run(self.app(scope, receive, send))
        return ASGIResponse(response_status, response_headers, bytes(response_body))

    def get(self, path: str, **kwargs) -> ASGIResponse:
        return self.request("GET", path, **kwargs)

    def post(self, path: str, **kwargs) -> ASGIResponse:
        return self.request("POST", path, **kwargs)

    def patch(self, path: str, **kwargs) -> ASGIResponse:
        return self.request("PATCH", path, **kwargs)


class DarkLensBackendIntegrationTests(unittest.TestCase):
    client: ASGIClient

    @classmethod
    def setUpClass(cls) -> None:
        ROOT.joinpath("tmp").mkdir(parents=True, exist_ok=True)
        if TEST_DB.exists():
            TEST_DB.unlink()

        init_db()
        with session() as db:
            seed_nightjar(db, reset=True)

        cls.client = ASGIClient(app)

    @classmethod
    def tearDownClass(cls) -> None:
        if TEST_DB.exists():
            TEST_DB.unlink()

    # --------------------------------------------------------------------------
    # Route 1: GET /api/health
    # --------------------------------------------------------------------------
    def test_01_get_health(self):
        resp = self.client.get("/api/health")
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertEqual(data.get("status"), "ok")
        self.assertTrue(data.get("synthetic_data_only"))

    # --------------------------------------------------------------------------
    # Route 2: GET /api/cases
    # --------------------------------------------------------------------------
    def test_02_get_cases(self):
        resp = self.client.get("/api/cases")
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertIsInstance(data, list)
        self.assertGreaterEqual(len(data), 1)
        nightjar = next((c for c in data if c["id"] == "NIGHTJAR-2026-001"), None)
        self.assertIsNotNone(nightjar)
        self.assertTrue(nightjar["synthetic"])
        self.assertEqual(nightjar["status"], "open")

    # --------------------------------------------------------------------------
    # Route 3: POST /api/cases/preview
    # --------------------------------------------------------------------------
    def test_03_preview_case_success(self):
        bundle_path = ROOT / "test_cases" / "valid_case_bundle_template.json"
        bundle = json.loads(bundle_path.read_text(encoding="utf-8"))
        resp = self.client.post("/api/cases/preview", json_data=bundle)
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertTrue(data.get("valid"))
        self.assertEqual(data.get("counts", {}).get("sources"), 1)
        self.assertEqual(data.get("counts", {}).get("entities"), 2)

    def test_04_preview_case_missing_fields_422(self):
        resp = self.client.post("/api/cases/preview", json_data={"case": {}})
        self.assertEqual(resp.status_code, 422)
        data = resp.json()
        detail = data.get("detail", [])
        self.assertTrue(any("schema_version" in str(d) for d in detail))

    def test_05_preview_case_malformed_json_422(self):
        resp = self.client.post(
            "/api/cases/preview",
            data=b'{"broken_json": [}',
            headers={"content-type": "application/json"},
        )
        self.assertEqual(resp.status_code, 422)

    # --------------------------------------------------------------------------
    # Route 4: POST /api/cases/import
    # --------------------------------------------------------------------------
    def test_06_import_case_success(self):
        bundle_path = ROOT / "test_cases" / "valid_hollowreed_case.json"
        bundle = json.loads(bundle_path.read_text(encoding="utf-8"))
        resp = self.client.post("/api/cases/import", json_data=bundle)
        self.assertEqual(resp.status_code, 201)
        data = resp.json()
        self.assertEqual(data.get("case", {}).get("id"), "CASE-2026-002")
        self.assertEqual(data.get("entity_count"), 17)
        self.assertGreaterEqual(data.get("candidate_link_count"), 1)

    def test_07_import_case_duplicate_409(self):
        bundle_path = ROOT / "test_cases" / "valid_hollowreed_case.json"
        bundle = json.loads(bundle_path.read_text(encoding="utf-8"))
        resp = self.client.post("/api/cases/import", json_data=bundle)
        self.assertEqual(resp.status_code, 409)
        data = resp.json()
        self.assertIn("already exists", str(data.get("detail")))

    def test_08_import_case_bad_schema_422(self):
        bundle_path = ROOT / "test_cases" / "bad_missing_schema_version.json"
        bundle = json.loads(bundle_path.read_text(encoding="utf-8"))
        resp = self.client.post("/api/cases/import", json_data=bundle)
        self.assertEqual(resp.status_code, 422)
        data = resp.json()
        self.assertTrue(any("schema_version" in str(err) for err in data.get("detail", [])))

    def test_09_import_case_bad_reliability_422(self):
        bundle_path = ROOT / "test_cases" / "bad_reliability_out_of_bounds.json"
        bundle = json.loads(bundle_path.read_text(encoding="utf-8"))
        resp = self.client.post("/api/cases/import", json_data=bundle)
        self.assertEqual(resp.status_code, 422)
        data = resp.json()
        self.assertTrue(any("reliability" in str(err).lower() for err in data.get("detail", [])))

    def test_10_import_case_unknown_entity_422(self):
        bundle_path = ROOT / "test_cases" / "bad_unknown_entity_id.json"
        bundle = json.loads(bundle_path.read_text(encoding="utf-8"))
        resp = self.client.post("/api/cases/import", json_data=bundle)
        self.assertEqual(resp.status_code, 422)
        data = resp.json()
        self.assertTrue(any("unknown-entity-999" in str(err).lower() for err in data.get("detail", [])))

    def test_11_import_case_bad_data_mode_422(self):
        bundle_path = ROOT / "test_cases" / "bad_data_mode.json"
        bundle = json.loads(bundle_path.read_text(encoding="utf-8"))
        resp = self.client.post("/api/cases/import", json_data=bundle)
        self.assertEqual(resp.status_code, 422)
        data = resp.json()
        self.assertTrue(any("data_mode" in str(err).lower() for err in data.get("detail", [])))

    # --------------------------------------------------------------------------
    # Route 5: GET /api/cases/{case_id}
    # --------------------------------------------------------------------------
    def test_12_get_case_payload_success(self):
        resp = self.client.get("/api/cases/NIGHTJAR-2026-001")
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertEqual(data["case"]["id"], "NIGHTJAR-2026-001")
        self.assertIn("entities", data)
        self.assertIn("sources", data)
        self.assertIn("evidence", data)
        self.assertIn("links", data)
        self.assertIn("audit_events", data)
        self.assertIn("evidence_associations", data)
        # Check that dossiers are populated
        self.assertTrue(all("dossier" in link for link in data["links"]))

    def test_13_get_case_payload_not_found_404(self):
        resp = self.client.get("/api/cases/UNKNOWN-CASE-999")
        self.assertEqual(resp.status_code, 404)
        data = resp.json()
        self.assertIn("not found", str(data.get("detail", "")).lower())

    # --------------------------------------------------------------------------
    # Route 6: GET /api/cases/{case_id}/timeline
    # --------------------------------------------------------------------------
    def test_14_get_timeline_success(self):
        resp = self.client.get("/api/cases/NIGHTJAR-2026-001/timeline")
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertIsInstance(data, list)
        self.assertEqual(len(data), 24)
        self.assertTrue(all("observed_at" in event for event in data))

    def test_15_get_timeline_not_found_404(self):
        resp = self.client.get("/api/cases/NONEXISTENT/timeline")
        self.assertEqual(resp.status_code, 404)

    # --------------------------------------------------------------------------
    # Route 7: GET /api/cases/{case_id}/analysis (Preview)
    # --------------------------------------------------------------------------
    def test_16_get_analysis_preview_success(self):
        resp = self.client.get("/api/cases/NIGHTJAR-2026-001/analysis")
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertIn("suggestions", data)
        self.assertIn("evidence_associations", data)
        self.assertIn("limitations", data)

    def test_17_get_analysis_preview_not_found_404(self):
        resp = self.client.get("/api/cases/UNKNOWN/analysis")
        self.assertEqual(resp.status_code, 404)

    # --------------------------------------------------------------------------
    # Route 8: POST /api/cases/{case_id}/analysis (Save/Refresh)
    # --------------------------------------------------------------------------
    def test_18_post_analysis_save_idempotence(self):
        # Run analysis save on CASE-2026-002
        resp1 = self.client.post("/api/cases/CASE-2026-002/analysis")
        self.assertEqual(resp1.status_code, 200)
        data1 = resp1.json()
        initial_links = data1["candidate_link_count"]

        # Run again, should be completely idempotent (0 added)
        resp2 = self.client.post("/api/cases/CASE-2026-002/analysis")
        self.assertEqual(resp2.status_code, 200)
        data2 = resp2.json()
        self.assertEqual(data2["added_count"], 0)
        self.assertEqual(data2["candidate_link_count"], initial_links)

    # --------------------------------------------------------------------------
    # Route 9: PATCH /api/links/{link_id}/review
    # --------------------------------------------------------------------------
    def test_19_patch_link_review_success(self):
        payload = {"status": "accepted", "note": "Integration test approval note"}
        resp = self.client.patch("/api/links/L1/review", json_data=payload)
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertEqual(data["review_status"], "accepted")

        # Verify audit event logged
        resp_case = self.client.get("/api/cases/NIGHTJAR-2026-001")
        self.assertEqual(resp_case.status_code, 200)
        case_data = resp_case.json()
        latest_audit = case_data["audit_events"][0]
        self.assertEqual(latest_audit["target_id"], "L1")
        self.assertIn("accepted", latest_audit["action"])
        self.assertEqual(latest_audit["note"], "Integration test approval note")

    def test_20_patch_link_review_not_found_404(self):
        payload = {"status": "rejected", "note": "Invalid link"}
        resp = self.client.patch("/api/links/NONEXISTENT-LINK/review", json_data=payload)
        self.assertEqual(resp.status_code, 404)

    def test_21_patch_link_review_invalid_status_422(self):
        payload = {"status": "confirmed_fraud", "note": "Illegal status value"}
        resp = self.client.patch("/api/links/L1/review", json_data=payload)
        self.assertEqual(resp.status_code, 422)

    # --------------------------------------------------------------------------
    # Route 10: GET /api/cases/{case_id}/export.json
    # --------------------------------------------------------------------------
    def test_22_export_json_success(self):
        resp = self.client.get("/api/cases/NIGHTJAR-2026-001/export.json")
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertIn("case", data)
        self.assertIn("exported_at", data["case"])

    def test_23_export_json_not_found_404(self):
        resp = self.client.get("/api/cases/NONEXISTENT/export.json")
        self.assertEqual(resp.status_code, 404)

    # --------------------------------------------------------------------------
    # Route 11: GET /api/cases/{case_id}/export.csv?kind={kind}
    # --------------------------------------------------------------------------
    def test_24_export_csv_kinds(self):
        for kind in ("entities", "evidence", "links", "audit"):
            resp = self.client.get(f"/api/cases/NIGHTJAR-2026-001/export.csv?kind={kind}")
            self.assertEqual(resp.status_code, 200, f"CSV export failed for kind: {kind}")
            self.assertIn("text/csv", resp.headers.get("content-type", ""))
            self.assertTrue(len(resp.text) > 0)
            first_line = resp.text.splitlines()[0]
            self.assertIn(",", first_line)

    def test_25_export_csv_not_found_404(self):
        resp = self.client.get("/api/cases/NONEXISTENT/export.csv?kind=links")
        self.assertEqual(resp.status_code, 404)

    # --------------------------------------------------------------------------
    # Route 12: GET /api/cases/{case_id}/report.md
    # --------------------------------------------------------------------------
    def test_26_export_report_md_success(self):
        resp = self.client.get("/api/cases/NIGHTJAR-2026-001/report.md")
        self.assertEqual(resp.status_code, 200)
        self.assertIn("text/markdown", resp.headers.get("content-type", ""))
        self.assertIn("# DarkLens case report: NIGHTJAR-2026-001", resp.text)
        self.assertIn("## Case summary", resp.text)
        self.assertIn("## Candidate links", resp.text)
        self.assertIn("Supporting evidence provenance:", resp.text)

    def test_27_export_report_md_not_found_404(self):
        resp = self.client.get("/api/cases/NONEXISTENT/report.md")
        self.assertEqual(resp.status_code, 404)

    # --------------------------------------------------------------------------
    # Reset Determinism & Identical IDs / Counts
    # --------------------------------------------------------------------------
    def test_28_db_reset_and_reload_determinism(self):
        """Confirm resetting the DB and reloading the same case gives identical IDs and row counts."""
        with session() as db:
            orig_counts = {
                table: db.execute(f"SELECT COUNT(*) FROM {table} WHERE case_id='NIGHTJAR-2026-001'").fetchone()[0]
                for table in ("entities", "sources", "evidence", "links")
            }
            orig_link_ids = [r[0] for r in db.execute("SELECT id FROM links WHERE case_id='NIGHTJAR-2026-001' ORDER BY id").fetchall()]

            # Reset Nightjar
            seed_nightjar(db, reset=True)

            new_counts = {
                table: db.execute(f"SELECT COUNT(*) FROM {table} WHERE case_id='NIGHTJAR-2026-001'").fetchone()[0]
                for table in ("entities", "sources", "evidence", "links")
            }
            new_link_ids = [r[0] for r in db.execute("SELECT id FROM links WHERE case_id='NIGHTJAR-2026-001' ORDER BY id").fetchall()]

        self.assertEqual(orig_counts, new_counts)
        self.assertEqual(orig_link_ids, new_link_ids)


if __name__ == "__main__":
    unittest.main()
