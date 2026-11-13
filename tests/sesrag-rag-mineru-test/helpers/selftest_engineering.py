"""本轮测试工程离线回归，不使用Docker或外部服务。"""

import json
import unittest
from types import SimpleNamespace

from helpers.live_cases import LiveCase


class UploadBudgetTests(unittest.TestCase):
    def live(self, embedding=True):
        live = LiveCase.__new__(LiveCase)
        live.case = SimpleNamespace(
            context={"real_capabilities": ["embedding"] if embedding else []}, case_id="TEST"
        )
        live.input = lambda *a, **k: (b"abc" * 100, "fixed.pdf")
        live.base = lambda: "kb"
        live.reservations = []
        live.reserve = lambda kind, amount=1: live.reservations.append((kind, amount))
        live.requests = []

        def stop(*args, **kwargs):
            live.requests.append(kwargs)
            raise RuntimeError("STOP_BEFORE_NETWORK")

        live.request = stop
        return live

    def test_frozen_cap_matches_reservation(self):
        live = self.live()
        with self.assertRaisesRegex(RuntimeError, "STOP"):
            live.upload(".pdf")
        cap = dict(live.reservations)["document_chunks"]
        self.assertEqual(cap, 128)
        self.assertEqual(json.loads(live.requests[0]["data"]["chunker"])["max_chunks"], cap)

    def test_actual_http_route_freezes_live_case_cap(self):
        from pathlib import Path
        from tempfile import TemporaryDirectory

        from fastapi.testclient import TestClient

        from backend.app import create_app
        from backend.config import Settings
        from backend.db.rag_models import IndexBuildModel

        live = self.live()
        with self.assertRaises(RuntimeError):
            live.upload(".pdf")
        data = live.requests[0]["data"].copy()
        with TemporaryDirectory() as directory:
            root = Path(directory)
            settings = Settings(
                database_url=f"sqlite+aiosqlite:///{root / 'cap.db'}",
                upload_dir=str(root / "uploads"),
                rag_artifact_dir=str(root / "artifacts"),
                rag_tmp_dir=str(root / "tmp"),
                auto_create_schema=True,
                redis_enabled=False,
                _env_file=None,
            )
            app = create_app(settings)
            with TestClient(app) as client:
                base = client.post(
                    "/api/v3/knowledge-bases",
                    json={
                        "name": "cap-link",
                        "embedding_profile_id": "mock-embedding",
                        "embedding_profile_version": 1,
                    },
                    headers={"Idempotency-Key": "cap-base"},
                ).json()["knowledge_base_id"]
                data.update(knowledge_base_id=base, parse="{}")
                response = client.post(
                    "/api/v3/documents",
                    data=data,
                    files={"file": ("cap.txt", b"source fact", "text/plain")},
                    headers={"Idempotency-Key": "cap-upload"},
                )
                self.assertEqual(response.status_code, 202, response.text)
                batch = response.json()["latest_build"]["index_batch_id"]

                async def snapshot():
                    async with app.state.session_factory() as session:
                        return (await session.get(IndexBuildModel, batch)).chunker_snapshot

                self.assertEqual(
                    client.portal.call(snapshot)["max_chunks"],
                    dict(live.reservations)["document_chunks"],
                )

    def test_rejected_reservation_never_uploads(self):
        live = self.live()

        def reject(*args):
            raise ValueError("EXHAUSTED")

        live.reserve = reject
        with self.assertRaises(ValueError):
            live.upload(".pdf")
        self.assertEqual(live.requests, [])

    def test_parse_only_does_not_reserve_embedding(self):
        live = self.live(False)
        with self.assertRaises(RuntimeError):
            live.upload(".pdf")
        self.assertNotIn("document_chunks", dict(live.reservations))


class AnnotationTests(unittest.TestCase):
    def test_frozen_original_annotations(self):
        from helpers.common import SUITE, load
        from helpers.source_annotations import audit_annotations

        self.assertEqual(
            audit_annotations(load(SUITE / "fixtures/source-annotations.json"))["questions"], 25
        )

    def test_binding_refuses_missing_and_ambiguous(self):
        from helpers.source_annotations import bind_source, sha

        value = {
            "sources": [{"source_sha256": "s", "format": "txt"}],
            "questions": [{"id": "q", "ranges": [{"source_sha256": "s", "quote": "fact"}]}],
        }
        for text in ("absent", "fact fact"):
            with self.assertRaises(ValueError):
                bind_source(value, "s", text, sha(text.encode()))
        row = bind_source(value, "s", "a fact", sha(b"a fact"))
        self.assertEqual(row["questions"][0]["relevant_ranges"][0]["start"], 2)


class MetricTests(unittest.TestCase):
    def test_recall_and_mrr_include_missed_questions(self):
        from helpers.evaluation_metrics import ranking_metrics

        result = ranking_metrics(
            {"q1": ["a", "b"], "q2": ["z"]}, {"q1": ["x", "b", "a"], "q2": ["x"]}, k=5
        )
        self.assertEqual(result["mean_recall"], 0.5)
        self.assertEqual(result["mrr"], 0.25)
        self.assertEqual(result["hit_question_rate"], 0.5)

    def test_duplicate_rank_and_missing_question_rejected(self):
        from helpers.evaluation_metrics import ranking_metrics

        for ranking in ({"q": ["a", "a"]}, {}):
            with self.assertRaises(ValueError):
                ranking_metrics({"q": ["a"]}, ranking, k=20)


class PdfInputTests(unittest.TestCase):
    def test_pdf_hash_metadata_selection_and_zero_paid_missing_target(self):
        from unittest.mock import Mock, patch

        from helpers.case_runner import Blocked

        metadata = {"scan-hash": {"scanned": True}, "text-hash": {"scanned": False}}

        def make(rows):
            live = LiveCase.__new__(LiveCase)

            def block(reason):
                raise Blocked(reason)

            live.case = SimpleNamespace(block=block, note=Mock())
            live.plan = {"files": rows}
            live.budget = SimpleNamespace(approved_input=Mock(return_value=b"approved"))
            live.reserve, live.request = Mock(), Mock()
            return live

        scan = {"file": "ordinary.pdf", "sha256": "scan-hash"}
        text = {"file": "misleading-scan.pdf", "sha256": "text-hash"}
        with patch("helpers.live_cases.load", return_value={"inputs": metadata}):
            for row, requested in ((scan, False), (text, True)):
                live = make([row])
                with self.assertRaises(Blocked):
                    live.upload(".pdf", scanned=requested)
                live.reserve.assert_not_called()
                live.request.assert_not_called()
                live.budget.approved_input.assert_not_called()
            for rows in ([scan], [text], [text, scan]):
                for scanned in (False, True):
                    target = scan if scanned else text
                    if target not in rows:
                        continue
                    live = make(rows)
                    self.assertEqual(
                        live.input(".pdf", scanned=scanned), (b"approved", target["file"])
                    )
                    live.budget.approved_input.assert_called_once_with(target["file"])


class AdaptationTests(unittest.TestCase):
    def test_collector_allows_only_explicit_budget_empty(self):
        from helpers.evidence_capture import validate_capture

        self.assertEqual(validate_capture([], expect_evidence=False), [])
        with self.assertRaises(AssertionError):
            validate_capture([], expect_evidence=True)
        for expected in (False, True):
            with self.assertRaises(ValueError):
                validate_capture(["[非可信检索证据]fact"], expect_evidence=expected)
            self.assertEqual(
                validate_capture(["[S1] [非可信检索证据]fact"], expect_evidence=expected), [1]
            )

    def test_formal_interface_document_is_read_only_in_both_lanes(self):
        import yaml
        from helpers.common import ROOT, SUITE

        class Loader(yaml.SafeLoader):
            pass

        Loader.add_constructor(
            "!override",
            lambda loader, node: (
                loader.construct_sequence(node)
                if isinstance(node, yaml.SequenceNode)
                else loader.construct_mapping(node)
            ),
        )
        expected = "${SUITE_DIR}/../../docs/接口文档.md:/app/docs/接口文档.md:ro"
        for name in ("docker-compose.rag-test.yml", "docker-compose.rag-real.yml"):
            value = yaml.load((SUITE / "compose" / name).read_text(encoding="utf-8"), Loader=Loader)
            self.assertIn(expected, value["services"]["tools"]["volumes"])
            mounts = value["services"]["tools"]["volumes"]
            for compose_name in ("docker-compose.rag-test.yml", "docker-compose.rag-real.yml"):
                self.assertIn(
                    "${SUITE_DIR}/compose/"
                    + compose_name
                    + ":/suite/compose/"
                    + compose_name
                    + ":ro",
                    mounts,
                )
            self.assertFalse(any(mount.startswith("${SUITE_DIR}/compose:") for mount in mounts))
        self.assertTrue((ROOT / "docs/接口文档.md").is_file())

    def test_generated_columns_not_cloned(self):
        from helpers.synthetic_rows import values

        from backend.db.rag_models import IndexBuildModel

        row = IndexBuildModel(index_batch_id="batch", legacy_unverified=True)
        result = values(row, {"index_batch_id"})
        self.assertNotIn("legacy_unverified", result)
        self.assertNotIn("index_batch_id", result)

    def test_strict_evidence_prefix_and_source_number(self):
        from helpers.evidence_capture import evidence_prefix, source_number

        for text in ("[非可信检索证据]fact", "[S1] [非可信检索证据]fact"):
            self.assertTrue(evidence_prefix(text))
        for text in (
            "history [非可信检索证据]fact",
            "[Sx] [非可信检索证据]fact",
            "[S0] [非可信检索证据]fact",
        ):
            self.assertFalse(evidence_prefix(text))
        self.assertEqual(source_number("[S12] [非可信检索证据]fact"), 12)
        with self.assertRaises(ValueError):
            source_number("[非可信检索证据]fact")


class BoundaryTests(unittest.TestCase):
    def test_source_range_tampering_rejected(self):
        import copy

        from helpers.common import SUITE, load
        from helpers.source_annotations import audit_annotations

        value = copy.deepcopy(load(SUITE / "fixtures/source-annotations.json"))
        value["questions"][0]["ranges"][0]["start"] += 1
        with self.assertRaisesRegex(ValueError, "SOURCE_RANGE"):
            audit_annotations(value)

    def test_chunk_overlap_and_paired_decline(self):
        from helpers.evaluation_metrics import paired_metrics, relevant_chunks

        question = {
            "id": "q",
            "answerable": True,
            "relevant_ranges": [
                {"source_sha256": "s", "artifact_sha256": "h", "start": 3, "end": 7}
            ],
        }
        chunks = [
            {"chunk_id": "a", "source_sha256": "s", "artifact_sha256": "h", "start": 0, "end": 5},
            {"chunk_id": "b", "source_sha256": "s", "artifact_sha256": "h", "start": 5, "end": 10},
        ]
        self.assertEqual(relevant_chunks([question], chunks), {"q": ["a", "b"]})
        result = paired_metrics(
            {"q": ["a"]}, {"q": ["a", "x"]}, {"q": ["x", "a"]}, {"q": ["a", "x"]}
        )
        self.assertEqual(result["declined_questions"], ["q"])
        self.assertFalse(result["recommend_default"])

    def test_stats_timeout_missing_and_stop(self):
        import subprocess

        from helpers.resource_observation import ResourceSampler

        calls = []

        def timeout(args, **kwargs):
            calls.append((args, kwargs))
            raise subprocess.TimeoutExpired(args, 5)

        sampler = ResourceSampler(["a" * 64], runner=timeout, max_samples=1).start()
        sampler.thread.join(timeout=2)
        summary = sampler.stop()
        self.assertFalse(sampler.thread.is_alive())
        self.assertEqual(summary["failures"], 1)
        self.assertEqual(summary["missed_container_samples"], 1)
        self.assertEqual(calls[0][1]["timeout"], 5)
        self.assertEqual(calls[0][0][-1], "a" * 64)

    def test_stats_valid_sample_and_foreign_container(self):
        from helpers.resource_observation import ResourceSampler

        def runner(args, **kwargs):
            return SimpleNamespace(
                returncode=0,
                stdout=json.dumps({"ID": "a" * 12, "CPUPerc": "3.5%", "MemUsage": "2MiB / 8GiB"}),
            )

        sampler = ResourceSampler(["a" * 64, "b" * 64], runner=runner, max_samples=1).start()
        sampler.thread.join(timeout=2)
        summary = sampler.stop()
        self.assertEqual(summary["sampled_peak_memory_bytes"], 2 * 1024**2)
        self.assertEqual(summary["missed_container_samples"], 1)
        with self.assertRaises(ValueError):
            ResourceSampler(["not-an-owned-id"])


class ResourceTests(unittest.TestCase):
    def test_partial_sample_reports_missing_and_sampled_peak(self):
        from helpers.resource_observation import resource_summary

        value = resource_summary(
            [{"cpu_percent": 7.5, "memory_bytes": 1024, "container": "owned"}], failures=1, missed=2
        )
        self.assertEqual(value["sampled_peak_cpu_percent"], 7.5)
        self.assertEqual(value["failures"], 1)
        self.assertEqual(value["missed_container_samples"], 2)
        self.assertFalse(value["continuous_peak_proven"])

    def test_no_performance_execution_stays_not_run(self):
        from helpers.resource_observation import performance_summary

        self.assertEqual(performance_summary([], [])["status"], "not_run")


if __name__ == "__main__":
    unittest.main()
