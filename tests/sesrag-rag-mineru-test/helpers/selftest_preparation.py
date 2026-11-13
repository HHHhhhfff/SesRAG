"""任务1～2工程回归：只验证准备和准入，不执行产品用例或真实请求。"""

import copy
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from helpers.common import SUITE, digest, load
from helpers.preflight import real_gate


class PreparationTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.private = self.root / "runtime-inputs"
        self.private.mkdir()
        self.profiles = load(SUITE / "fixtures/profiles.real.example.json")
        self.models = load(SUITE / "fixtures/models.local.json")
        self.plan = load(SUITE / "fixtures/live-plan.example.json")
        self.plan.update(
            authorized=True,
            capabilities=["mineru"],
            files=[{"file": "office.docx", "sha256": digest(b"synthetic-office-input")}],
        )
        (self.private / "office.docx").write_bytes(b"synthetic-office-input")
        # 合成凭据仅验证存在性；本模块没有网络客户端或供应商请求。
        self.secrets = {
            "MINERU_ENABLED": "true",
            "MINERU_API_KEY": "synthetic-preparation-mineru",
            "MINERU_STATE_ENCRYPTION_KEY": "eHh4eHh4eHh4eHh4eHh4eHh4eHh4eHh4eHh4eHh4eHg=",
            "MINERU_STORAGE_HOST_ALLOWLIST": "storage.example.com",
        }

    def tearDown(self):
        self.temp.cleanup()

    def gate(self):
        for name, value in (
            ("profiles.real.json", self.profiles),
            ("models.real.json", self.models),
            ("secrets.json", self.secrets),
            ("plan.json", self.plan),
        ):
            (self.private / name).write_text(json.dumps(value), encoding="utf-8")
        with patch("helpers.preflight.SUITE", self.root):
            return real_gate(self.private / "plan.json", self.plan["plan"])

    def test_mineru_only_does_not_require_model_counters_or_keys(self):
        result = self.gate()
        self.assertTrue(result["passed"], result["reasons"])
        self.assertEqual(result["capabilities"], ["mineru"])
        self.assertFalse(result["full_business_scope"])
        self.assertNotIn("models.json", result["config_paths"])

    def test_missing_mineru_key_is_blocked(self):
        self.secrets.pop("MINERU_API_KEY")
        self.assertIn("MISSING_REAL_ALIAS_MINERU_API_KEY", self.gate()["reasons"])

    def test_unselected_secrets_are_not_forwarded(self):
        self.secrets["MODEL_API_KEY"] = "synthetic-unused-key"
        result = self.gate()
        self.assertTrue(result["passed"], result["reasons"])
        self.assertNotIn("MODEL_API_KEY", result["secrets"])

    def test_acceptance_cannot_omit_capabilities(self):
        self.plan["plan"] = "Acceptance"
        self.assertIn("ACCEPTANCE_REQUIRES_ALL_CAPABILITIES", self.gate()["reasons"])

    def test_legacy_plan_still_requires_full_business(self):
        self.plan.pop("capabilities")
        result = self.gate()
        self.assertFalse(result["passed"])
        self.assertIn("INPUT_COUNTER_UNVERIFIED_embedding", result["reasons"])
        self.assertIn("COUNTER_EVIDENCE_MISSING_generation", result["reasons"])

    def test_unknown_duplicate_and_empty_capabilities_rejected(self):
        for capabilities in (["other"], [], ["mineru", "mineru"], "mineru"):
            with self.subTest(capabilities=capabilities):
                self.plan["capabilities"] = capabilities
                self.assertIn("LIVE_CAPABILITIES_INVALID", self.gate()["reasons"])

    def test_approval_and_file_hash_remain_mandatory(self):
        self.plan["authorized"] = False
        self.plan["files"][0]["sha256"] = "0" * 64
        result = self.gate()
        self.assertIn("OUTBOUND_AUTHORIZATION_REQUIRED", result["reasons"])
        self.assertIn("LIVE_FILE_HASH_INVALID", result["reasons"])

    def test_input_cannot_escape_private_directory(self):
        self.plan["files"][0]["file"] = "../outside.docx"
        self.assertIn("LIVE_FILE_HASH_INVALID", self.gate()["reasons"])

    def test_generation_only_requires_its_own_counter(self):
        self.plan["capabilities"] = ["generation"]
        self.secrets = {"MODEL_API_KEY": "synthetic-generation"}
        self.plan["files"] = []
        self.assertIn("COUNTER_EVIDENCE_MISSING_generation", self.gate()["reasons"])
        self.assertNotIn("MINERU_DISABLED", self.gate()["reasons"])
        self.assertNotIn("INPUT_COUNTER_UNVERIFIED_embedding", self.gate()["reasons"])

    def test_generation_counter_must_match_selected_model(self):
        self.plan["capabilities"] = ["generation"]
        self.plan["files"] = []
        self.secrets = {"MODEL_API_KEY": "synthetic-generation"}
        self.models = [row for row in self.models if row["provider_kind"] == "openai_compatible"]
        evidence = {
            "status": "verified",
            "capability": "generation",
            "model": "wrong-model",
            "revision": "test-only",
            "algorithm": "synthetic-test-only",
            "source": "synthetic-test-only",
            "date": "2026-11-11",
            "applicable_limits": {"context": 128},
            "calibration_results": [{"passed": True, "input_sha256": "a" * 64}],
        }
        (self.private / "counter.json").write_text(json.dumps(evidence))
        self.plan["counter_evidence"] = [
            {
                "file": "counter.json",
                "sha256": digest((self.private / "counter.json").read_bytes()),
                "capability": "generation",
            }
        ]
        self.assertIn("COUNTER_EVIDENCE_MODEL_MISMATCH_generation", self.gate()["reasons"])

    def test_valid_generation_scope_projects_only_generation_budget(self):
        self.plan["capabilities"] = ["generation"]
        self.plan["files"] = []
        self.secrets = {"MODEL_API_KEY": "synthetic-generation"}
        self.models = [row for row in self.models if row["provider_kind"] == "openai_compatible"]
        self.models[0]["base_url"] = "https://api.example.com/v1"
        self.models[0]["max_output_tokens"] = self.plan["budget"]["max_output_tokens"]
        evidence = {
            "status": "verified",
            "capability": "generation",
            "model": "local-synthetic",
            "revision": "test-only",
            "algorithm": "synthetic-test-only",
            "source": "synthetic-test-only",
            "date": "2026-11-11",
            "applicable_limits": {"context": 128},
            "calibration_results": [{"passed": True, "input_sha256": "a" * 64}],
        }
        (self.private / "counter.json").write_text(json.dumps(evidence))
        self.plan["counter_evidence"] = [
            {
                "file": "counter.json",
                "sha256": digest((self.private / "counter.json").read_bytes()),
                "capability": "generation",
            }
        ]
        result = self.gate()
        self.assertTrue(result["passed"], result["reasons"])
        self.assertEqual(result["budget"]["cloud_jobs"], 0)
        self.assertEqual(result["budget"]["document_chunks"], 0)
        self.assertEqual(result["budget"]["answers"], 1)

    def test_generation_profile_cannot_exceed_approved_output_budget(self):
        # REAL_009/011：真实输出上限由Profile驱动，不能只校验计划里的数字。
        self.plan["capabilities"] = ["generation"]
        self.plan["files"] = []
        self.secrets = {"MODEL_API_KEY": "synthetic-generation"}
        self.models = [r for r in self.models if r["provider_kind"] == "openai_compatible"]
        self.models[0]["max_output_tokens"] = self.plan["budget"]["max_output_tokens"] + 1
        self.assertIn("GENERATION_OUTPUT_BUDGET_EXCEEDED", self.gate()["reasons"])

    def test_negative_or_unbounded_budget_is_rejected(self):
        for value in (-1, True, 9):
            self.plan["budget"]["cloud_jobs"] = value
            self.assertIn("LIVE_BUDGET_INVALID", self.gate()["reasons"])

    def test_chunk_budget_is_checked_conservatively_before_product_upload(self):
        # REAL_011：生产已冻结并强制max_chunks=128，按同一硬上限预留，不猜办公产物片数。
        from types import SimpleNamespace
        from unittest.mock import Mock

        from helpers.live_cases import LiveCase

        for extension, expected in ((".docx", 128), (".txt", 5)):
            live = LiveCase.__new__(LiveCase)
            live.case = SimpleNamespace(context={"real_capabilities": ["embedding"]})
            live.input = lambda *args, ext=extension, **kwargs: (b"hello", "sample" + ext)
            live.request = Mock()

            def reserve(kind, amount=1, bound=expected):
                if kind == "document_chunks":
                    self.assertEqual(amount, bound)
                    raise ValueError("TEST_BUDGET_EXHAUSTED")

            live.reserve = reserve
            with self.assertRaisesRegex(ValueError, "TEST_BUDGET_EXHAUSTED"):
                live.upload(extension)
            live.request.assert_not_called()

    def test_final_copied_config_must_match_approved_hash(self):
        import shutil

        from helpers.prepare_runtime import prepare

        approved = self.private / "models.json"
        approved.write_text("[]", encoding="utf8")
        real = {
            "secrets": {},
            "config_paths": {"models.json": approved},
            "config_hashes": {"models.json": digest(approved.read_bytes())},
        }
        original_copy = shutil.copyfile

        def corrupt(source, target):
            original_copy(source, target)
            if Path(source) == approved:
                Path(target).write_text('["changed"]', encoding="utf8")

        with (
            patch(
                "helpers.prepare_runtime.run_path",
                side_effect=lambda area, run: self.root / area / run,
            ),
            patch("helpers.prepare_runtime.shutil.copyfile", side_effect=corrupt),
        ):
            with self.assertRaisesRegex(ValueError, "LIVE_CONFIG_CHANGED_AFTER_APPROVAL"):
                prepare(
                    "rag-config-hash-test",
                    "project",
                    "real",
                    {k: k for k in ("app", "tools", "frontend")},
                    "owner",
                    real,
                )

    def test_environment_audit_failure_does_not_leave_passed_summary(self):
        from helpers.lifecycle_exercise import publish_audit

        target = self.root / "engineering.json"
        with patch("helpers.environment_cases.record", side_effect=ValueError("TEST_AUDIT_FAILED")):
            with self.assertRaisesRegex(ValueError, "TEST_AUDIT_FAILED"):
                publish_audit(target, "rag-engineering-test", [], "frozen")
        self.assertEqual(load(target)["status"], "failed")

    def test_real_failure_summary_cannot_remain_not_run(self):
        from helpers.orchestrate import finish

        report = {
            "mode": "Real",
            "run_id": "rag-summary-selftest",
            "categories": [{"category": "real-formats", "status": "failed"}],
            "real": "not_run",
            "reasons": [],
            "environment": "passed",
            "product": "not_run",
        }
        with (
            patch("helpers.orchestrate.cleanup_module.cleanup", return_value={"status": "passed"}),
            patch("helpers.orchestrate.summarize"),
        ):
            self.assertEqual(
                finish(report, {1}, {}, self.root / "ledger.json", self.root, [], {}), 1
            )
        self.assertEqual(report["real"], "failed")

    def test_config_hash_is_from_exact_bytes_used_for_validation(self):
        # REAL_011：校验后文件变化时，冻结的仍须是已校验A而非后来的B。
        from helpers.live_preflight import evaluate

        self.gate()  # 在临时私有目录准备合成资料，没有网络操作。
        target = self.private / "profiles.real.json"
        before = target.read_bytes()
        original = load

        def change_after_read(path):
            value = original(path)
            if path == target:
                path.write_text("[]", encoding="utf8")
            return value

        with patch("helpers.live_preflight.load", side_effect=change_after_read):
            result = evaluate(self.private / "plan.json", "Business", self.root)
        self.assertEqual(result["config_hashes"]["profiles.json"], digest(before))

    def test_mineru_state_key_must_be_32_bytes(self):
        self.secrets["MINERU_STATE_ENCRYPTION_KEY"] = "invalid-key"
        self.assertIn("MINERU_STATE_KEY_INVALID", self.gate()["reasons"])

    def test_planned_real_does_not_read_secret_or_build_images(self):
        from helpers import common, orchestrate
        from helpers.protocol import manifest

        planned_entries = copy.deepcopy(manifest())
        for entry in planned_entries.values():
            entry["status"], entry["cases"] = "planned", []

        def area_path(area, identity):
            return self.root / area / identity

        with (
            patch.object(orchestrate, "SUITE", self.root),
            patch.object(orchestrate, "run_path", side_effect=area_path),
            patch.object(orchestrate, "check_tools", return_value={}),
            patch.object(orchestrate, "engine_identity", return_value={}),
            patch.object(orchestrate, "manifest", return_value=planned_entries),
            patch.object(orchestrate.cleanup_module, "existing_resources", return_value={}),
            patch.object(orchestrate, "real_gate") as gate,
            patch.object(orchestrate, "images") as build,
            patch.object(orchestrate, "finish", return_value=3),
            patch.object(common, "COMMAND_SCRATCH", common.COMMAND_SCRATCH),
            patch.object(common, "PROCESS_LEDGER", common.PROCESS_LEDGER),
        ):
            code = orchestrate.main(
                [
                    "--mode",
                    "Real",
                    "--run-id",
                    "rag-preparation-planned",
                    "--allow-real-requests",
                    "--live-plan",
                    "never-read.json",
                ]
            )
            self.assertEqual(code, 3)
            gate.assert_not_called()
            build.assert_not_called()

    def test_baseline_identity_is_explicit_and_not_database_seed(self):
        from helpers.baseline import baseline

        value = baseline()
        self.assertNotEqual(value["owner"], value["other_owner"])
        self.assertFalse(value["seed_sql_required"])

    def test_bad_baseline_rejected_before_initialization(self):
        from helpers.baseline import baseline

        value = load(SUITE / "fixtures/baseline.json")
        for mutate in (
            lambda v: v.update(other_owner=v["owner"]),
            lambda v: v.update(seed_sql_required=True),
        ):
            changed = copy.deepcopy(value)
            mutate(changed)
            path = self.root / "baseline.json"
            path.write_text(json.dumps(changed))
            with self.assertRaisesRegex(ValueError, "BASELINE"):
                baseline(path)


if __name__ == "__main__":
    unittest.main(verbosity=2)
