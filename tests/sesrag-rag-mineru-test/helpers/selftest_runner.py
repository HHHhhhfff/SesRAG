"""环境工程正负自测，非产品case，不计入PRD通过数。"""

import copy
import json
import os
import secrets
import shutil
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from jsonschema import ValidationError

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from helpers.common import digest, run_path
from helpers.evidence import redact, scan
from helpers.protocol import manifest, validate_result


class RunnerTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.context = {"run_id": "rag-selftest-0001", "category": "catalog", "lane": "local"}
        self.case = {
            "case_id": "ENGINE_001",
            "requirements": ["RAG-001"],
            "test_points": ["TQ-RAG-CAT-001"],
        }
        (self.root / "proof.txt").write_text("安全合成证据", encoding="utf-8")
        self.result = {
            "schema_version": 1,
            **self.context,
            "cases": [
                {
                    **self.case,
                    "title": "仅运行器协议自测",
                    "status": "passed",
                    "duration_ms": 1,
                    "error_code": None,
                    "expected": "证据存在",
                    "actual": "证据存在",
                    "phases": ["准备", "检查"],
                    "evidence": [
                        {
                            "path": "proof.txt",
                            "sha256": digest((self.root / "proof.txt").read_bytes()),
                        }
                    ],
                }
            ],
        }

    def tearDown(self):
        self.temp.cleanup()

    def valid(self, value=None):
        return validate_result(
            value or self.result, self.context, {"cases": [self.case]}, self.root
        )

    def test_engineering_valid_report(self):
        self.assertEqual(self.valid(), ["passed"])

    def test_engineering_empty_report_rejected(self):
        self.result["cases"] = []
        with self.assertRaises(ValidationError):
            self.valid()

    def test_engineering_wrong_run_and_lane(self):
        for field, value in (
            ("run_id", "rag-other-0000"),
            ("lane", "real"),
            ("category", "vectors"),
        ):
            changed = copy.deepcopy(self.result)
            changed[field] = value
            with self.assertRaises(ValueError):
                self.valid(changed)

    def test_engineering_duplicate_case(self):
        self.result["cases"] *= 2
        with self.assertRaises(ValueError):
            self.valid()

    def test_engineering_missing_case(self):
        self.result["cases"][0]["case_id"] = "OTHER_001"
        with self.assertRaises(ValueError):
            self.valid()

    def test_engineering_bad_evidence_path(self):
        self.result["cases"][0]["evidence"][0]["path"] = "../escape.txt"
        with self.assertRaises(ValueError):
            self.valid()

    def test_engineering_bad_evidence_hash(self):
        self.result["cases"][0]["evidence"][0]["sha256"] = "a" * 64
        with self.assertRaises(ValueError):
            self.valid()

    def test_engineering_requirement_mismatch(self):
        self.result["cases"][0]["test_points"] = ["TQ-RAG-CAT-002"]
        with self.assertRaises(ValueError):
            self.valid()

    def test_engineering_run_path_escape(self):
        for identity in ("../escape", "rag-../../bad", "RAG-unsafe", "rag-short"):
            with self.assertRaises(ValueError):
                run_path("runtime", identity)

    def test_engineering_manifest_initial_planned(self):
        entries = manifest()
        self.assertEqual(len(entries), 15)
        for entry in entries.values():
            if entry["status"] == "planned":
                self.assertEqual(entry["cases"], [])

    def test_engineering_secret_scan(self):
        (self.root / "bad.txt").write_text("known-secret-123")
        with self.assertRaises(ValueError):
            scan(self.root, ["known-secret-123"])
        self.assertNotIn(
            "known-secret-123", redact("Bearer known-secret-123", ["known-secret-123"])
        )

    def test_engineering_cleanup_wrong_engine(self):
        from helpers.cleanup import cleanup

        path = self.root / "ledger.json"
        path.write_text(
            json.dumps(
                {
                    "run_id": "rag-selftest-engine",
                    "engine": {"daemon": "other"},
                    "projects": [],
                    "images": [],
                }
            )
        )
        with (
            patch("helpers.cleanup.engine_identity", return_value={"daemon": "actual"}),
            patch("helpers.cleanup.run_path", return_value=self.root),
            patch("helpers.cleanup.command") as mutation,
        ):
            result = cleanup(path)
            self.assertEqual(result["status"], "failed")
            mutation.assert_not_called()

    def test_engineering_unverified_guard_not_bypassed(self):
        from helpers.common import SUITE, load

        from backend.infrastructure.providers.rag_registry import (
            embedding_from_profile,
            rerank_from_profile,
        )

        for row in load(SUITE / "fixtures/profiles.real.example.json"):
            if (
                row["kind"] in {"embedding", "rerank"}
                and row["config"].get("adapter_kind") == "bailian"
            ):
                function = (
                    embedding_from_profile if row["kind"] == "embedding" else rerank_from_profile
                )
                with self.assertRaises(Exception) as error:
                    function(row)
                self.assertEqual(error.exception.code, "INPUT_COUNTER_UNVERIFIED")

    def test_engineering_command_timeout(self):
        from helpers.common import command

        with self.assertRaises(RuntimeError):
            command([sys.executable, "-c", "import time; time.sleep(10)"], timeout=0.3)

    def test_engineering_exited_process_is_not_active(self):
        import subprocess

        from helpers.common import process_token

        self.assertIsNotNone(process_token(os.getpid()))
        # 保持Popen句柄存活，覆盖Windows已退出对象仍可查询创建时间的窗口。
        with subprocess.Popen([sys.executable, "-c", "pass"]) as process:
            process.wait(timeout=10)
            self.assertIsNone(process_token(process.pid))
            if os.name == "nt":
                self.assertIsNotNone(process_token(process.pid, include_exited=True))

    def test_engineering_frozen_archive_escape_rejected_before_read(self):
        from helpers.builds import images

        cache = self.root / ".cache/frozen-builds/engineering"
        cache.mkdir(parents=True)
        (cache / "build.json").write_text(
            json.dumps(
                {
                    "build_source": "fixture-source",
                    "images": {"app": {"archive": "../outside.tar"}},
                }
            )
        )
        with patch("helpers.builds.SUITE", self.root), patch("helpers.builds.command") as docker:
            with self.assertRaisesRegex(ValueError, "FROZEN_ARCHIVE_PATH_INVALID"):
                images(
                    {"run_id": "rag-selftest-archive"},
                    self.root / "ledger.json",
                    {"build_source": "fixture-source"},
                    "engineering",
                )
            docker.assert_not_called()

    def test_engineering_browser_download_resumes_partial_package(self):
        import base64
        import hashlib
        import io
        import threading
        import time
        import zipfile
        from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

        from helpers.download_browser import fetch

        stream = io.BytesIO()
        with zipfile.ZipFile(stream, "w") as archive:
            archive.writestr("fixture.txt", "environment-only")
        package = stream.getvalue()
        offsets = []

        class Download(BaseHTTPRequestHandler):
            def do_HEAD(self):
                self.send_response(200)
                self.send_header("Content-Length", str(len(package)))
                checksum = base64.b64encode(hashlib.md5(package).digest()).decode()
                self.send_header("x-goog-hash", "crc32c=fixture, md5=" + checksum)
                self.end_headers()

            def do_GET(self):
                offset = int(self.headers.get("Range", "bytes=0-").split("=")[1].split("-")[0])
                offsets.append(offset)
                self.send_response(206 if offset else 200)
                self.send_header("Content-Length", str(len(package) - offset))
                if offset:
                    self.send_header(
                        "Content-Range", f"bytes {offset}-{len(package) - 1}/{len(package)}"
                    )
                self.end_headers()
                self.wfile.write(package[offset:] if offset else package[:32])
                self.close_connection = True

            def log_message(self, *_):
                pass

        server = ThreadingHTTPServer(("127.0.0.1", 0), Download)
        worker = threading.Thread(target=server.serve_forever, daemon=True)
        worker.start()
        try:
            target = self.root / "browser.zip"
            fetch(
                f"http://127.0.0.1:{server.server_port}/fixture.zip", target, time.monotonic() + 10
            )
            self.assertEqual(target.read_bytes(), package)
            self.assertEqual(offsets, [0, 32])
        finally:
            server.shutdown()
            server.server_close()
            worker.join(timeout=5)

    def test_engineering_frozen_import_intent_survives_load_failure(self):
        from helpers.builds import images
        from helpers.common import load

        cache = self.root / ".cache/frozen-builds/engineering"
        cache.mkdir(parents=True)
        package = b"engineering archive placeholder"
        (cache / "app.tar").write_bytes(package)
        expected_id = "sha256:" + "a" * 64
        (cache / "build.json").write_text(
            json.dumps(
                {
                    "build_source": "fixture-source",
                    "images": {
                        "app": {
                            "archive": "app.tar",
                            "sha256": digest(package),
                            "id": expected_id,
                            "tag": "sesrag-rag-test:rag-selftest-original-app",
                        }
                    },
                }
            )
        )
        ledger_path = self.root / "ledger.json"
        with (
            patch("helpers.builds.SUITE", self.root),
            patch(
                "helpers.builds.command",
                side_effect=[(1, ""), RuntimeError("synthetic-load-failure")],
            ),
        ):
            with self.assertRaisesRegex(RuntimeError, "synthetic-load-failure"):
                images(
                    {"run_id": "rag-selftest-current"},
                    ledger_path,
                    {"build_source": "fixture-source"},
                    "engineering",
                )
        saved = load(ledger_path)
        self.assertEqual(saved["images"][0]["id"], expected_id)
        self.assertEqual(saved["temporary_import_tags"][0]["id"], expected_id)
        self.assertTrue(saved["temporary_import_tags"][0]["absent_before_load"])

    def test_engineering_control_persistence_and_rejects(self):
        from fastapi.testclient import TestClient
        from harness import scenario_control as control

        with (
            patch.object(control, "DB", self.root / "control.sqlite"),
            patch.dict(os.environ, {"TEST_CONTROL_TOKEN": "dummy-control"}),
        ):
            client = TestClient(control.app)
            headers = {"Authorization": "Bearer dummy-control"}
            self.assertEqual(client.put("/plans/task-a/embedding", json=[{}]).status_code, 403)
            self.assertEqual(
                client.put(
                    "/plans/task-a/embedding", json=[{"code": "exec"}], headers=headers
                ).status_code,
                422,
            )
            self.assertEqual(
                client.put(
                    "/plans/task-a/embedding", json=[{"status": 429}, {}], headers=headers
                ).status_code,
                200,
            )
            self.assertEqual(
                client.post("/step/task-a/embedding", json={}, headers=headers).json()["action"][
                    "status"
                ],
                429,
            )
            self.assertEqual(
                client.post("/step/task-a/embedding", json={}, headers=headers).json()["action"], {}
            )
            fresh = TestClient(control.app)
            observed = fresh.get("/observations/task-a", headers=headers).json()
            self.assertEqual(observed["calls"]["embedding"]["count"], 2)

    def test_engineering_real_template_cannot_authorize(self):
        from helpers.preflight import real_gate

        private = self.root / "runtime-inputs"
        private.mkdir()
        plan = private / "plan.json"
        plan.write_text(json.dumps({"schema_version": 1, "plan": "Business", "authorized": False}))
        with patch("helpers.preflight.SUITE", self.root):
            result = real_gate(plan, "Business")
        self.assertFalse(result["passed"])
        self.assertIn("OUTBOUND_AUTHORIZATION_REQUIRED", result["reasons"])
        self.assertIn("THREE_CAPABILITY_COUNTER_EVIDENCE_REQUIRED", result["reasons"])

    def test_engineering_safehttp_still_rejects_private_protocol(self):
        from backend.application.errors import PermanentTaskError
        from backend.infrastructure.rag.download_safety import SafeHTTP

        with self.assertRaises(PermanentTaskError):
            SafeHTTP(["mineru.net"]).validate("http://127.0.0.1/internal")

    def test_engineering_package_fixtures_use_real_normalizer(self):
        from harness.transport_fixtures import package

        from backend.application.errors import PermanentTaskError
        from backend.infrastructure.rag.mineru_outputs import normalize_package

        self.assertIn("ALPHA", normalize_package(package("safe"), ".docx").text)
        for kind in ("escape", "nested", "empty"):
            with self.assertRaises(PermanentTaskError):
                normalize_package(package(kind), ".docx")

    def test_engineering_control_unknown_actions_rejected(self):
        from fastapi.testclient import TestClient
        from harness import scenario_control as control

        with (
            patch.object(control, "DB", self.root / "control.sqlite"),
            patch.dict(os.environ, {"TEST_CONTROL_TOKEN": "dummy-control"}),
        ):
            client = TestClient(control.app)
            headers = {"Authorization": "Bearer dummy-control"}
            self.assertEqual(
                client.put("/plans/task-a/unknown", json=[{}], headers=headers).status_code, 422
            )
            self.assertEqual(
                client.put(
                    "/plans/task-a/embedding", json=[{"delay_seconds": 121}], headers=headers
                ).status_code,
                422,
            )

    @unittest.skipUnless(shutil.which("docker"), "Compose结构核验由宿主执行，tools无Docker socket")
    def test_engineering_compose_real_override(self):
        from helpers.cleanup import erase_run_directory
        from helpers.common import command
        from helpers.orchestrate import compose_args, inspect_config
        from helpers.prepare_runtime import prepare

        identity = "rag-config-probe-" + secrets.token_hex(6)
        images = {
            kind: "sesrag-rag-test:config-only-" + kind for kind in ("app", "frontend", "tools")
        }
        try:
            for lane in ("local", "real"):
                project = "sesrag-" + identity + "-" + lane
                directory, _ = prepare(identity, project, lane, images, "config-owner")
                raw = command(
                    [*compose_args(project, directory, lane), "config", "--format", "json"]
                )[1]
                self.assertEqual(inspect_config(json.loads(raw), lane, project)["status"], "passed")
        finally:
            erase_run_directory("runtime", identity)

    def test_engineering_live_budget_cannot_refund_unknown(self):
        from helpers.live_budget import LiveBudget

        plan = self.root / "plan.json"
        plan.write_text(
            json.dumps({"budget": {"cloud_jobs": 1, "timeout_seconds": 60}, "files": []})
        )
        budget = LiveBudget(plan, self.root / "budget.sqlite")
        budget.reserve("cloud_jobs")
        with self.assertRaisesRegex(ValueError, "EXHAUSTED"):
            budget.reserve("cloud_jobs")


if __name__ == "__main__":
    unittest.main(verbosity=2)
