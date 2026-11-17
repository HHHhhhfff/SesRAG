# 模块独立导入需先加入父目录。
# ruff: noqa: E402
"""005 生命周期不变量，使用可控 Docker 替身验证拒绝路径。"""

import sys
import unittest
from pathlib import Path

MODULE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(MODULE))
from helpers.lifecycle import checked_child, owned, verify_manifest
from helpers.preflight import MonitoringError


class LifecycleTests(unittest.TestCase):
    def test_rehashed_backup_cannot_redirect_bind_mounts_or_replace_generated_config(self):
        import tempfile

        from helpers.lifecycle import Environment, source_snapshot
        from helpers.preflight import digest, load, validate_image_lock
        from helpers.render import render, write_json

        with tempfile.TemporaryDirectory() as directory:
            e = Environment.__new__(Environment)
            e.environment = "local"
            e.path = Path(directory) / "local"
            e.images = validate_image_lock(load(MODULE / "images.lock.json"))
            write_json(
                e.path / "inputs/application-contract.json",
                load(MODULE / "integration/application-contract.example.json"),
            )
            e.state = {
                "environment": "local",
                "owner": "a" * 32,
                "port": 3000,
                "host_otlp": False,
                "platform": "docker-desktop",
                "tool_image": "",
                "image_lock_hash": digest(MODULE / "images.lock.json"),
                "source_hashes": source_snapshot(),
            }
            e.state["generated_hashes"] = render(
                load(e.path / "inputs/application-contract.json"), e.path / "generated"
            )
            e.write_env()
            e.check_drift()
            env = e.path / "monitoring.env"
            text = env.read_text(encoding="utf-8")
            env.write_text(text.replace("OBS_SECRET=", "OBS_SECRET=/unapproved/"), encoding="utf-8")
            e.state["env_hash"] = digest(env)
            with self.assertRaises(MonitoringError) as context:
                e.check_drift()
            self.assertEqual(context.exception.code, "OBS005_ENV_BINDING")
            e.write_env()
            config = e.path / "generated/config.alloy"
            config.write_text(
                config.read_text(encoding="utf-8").replace(
                    "http://loki:3100", "http://unapproved:3100"
                ),
                encoding="utf-8",
            )
            e.state["generated_hashes"]["config.alloy"] = digest(config)
            with self.assertRaises(MonitoringError) as context:
                e.check_drift()
            self.assertEqual(context.exception.code, "OBS005_GENERATED_BINDING")

    def test_ownership_needs_project_module_environment_and_nonce(self):
        labels = {
            "com.docker.compose.project": "sesrag-observe-local",
            "io.sesrag.observability.module": "obs005",
            "io.sesrag.observability.environment": "local",
            "io.sesrag.observability.owner": "nonce",
        }
        for key in labels:
            bad = dict(labels)
            bad[key] = "foreign"
            self.assertFalse(owned(bad, "local", "nonce"))
        self.assertTrue(owned(labels, "local", "nonce"))

    def test_recursive_mutation_cannot_escape_controlled_root(self):
        root = MODULE / "runtime"
        self.assertEqual(checked_child(root, root / "local"), (root / "local").resolve())
        for path in (root, root.parent, root / ".." / "other"):
            with self.assertRaises(MonitoringError):
                checked_child(root, path)

    def test_incomplete_or_altered_backup_rejected_before_restore(self):
        import json
        import tempfile

        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory)
            (path / "manifest.json").write_text(json.dumps({"complete": False}))
            with self.assertRaises(MonitoringError):
                verify_manifest(path, {})

    def test_stderr_never_enters_public_exception(self):

        from helpers.lifecycle import Environment

        e = Environment.__new__(Environment)
        e.deadline = None
        e.report = {}
        with self.assertRaises(MonitoringError) as context:
            e.run(
                [
                    sys.executable,
                    "-c",
                    'import sys;sys.stderr.write("SENSITIVE_SENTINEL D:/private/file");sys.exit(1)',
                ]
            )
        self.assertNotIn("SENSITIVE_SENTINEL", str(context.exception))
        self.assertNotIn("D:/private", str(context.exception))

    def test_complete_backup_tamper_and_unsafe_archive_rejected(self):
        import hashlib
        import json
        import tarfile
        import tempfile

        from helpers.preflight import VOLUMES

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            for name in (*VOLUMES, "runtime"):
                with tarfile.open(root / (name + ".tar.gz"), "w:gz") as archive:
                    item = tarfile.TarInfo(".")
                    item.type = tarfile.DIRTYPE
                    archive.addfile(item)
            files = {
                p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in root.glob("*.tar.gz")
            }
            manifest = {"complete": True, "images": {}, "files": files}
            (root / "manifest.json").write_text(json.dumps(manifest))
            verify_manifest(root, {})
            (root / "grafana_data.tar.gz").write_bytes(b"tampered")
            with self.assertRaises(MonitoringError):
                verify_manifest(root, {})
            with tarfile.open(root / "grafana_data.tar.gz", "w:gz") as archive:
                archive.addfile(tarfile.TarInfo("../escape"))
            manifest["files"]["grafana_data.tar.gz"] = hashlib.sha256(
                (root / "grafana_data.tar.gz").read_bytes()
            ).hexdigest()
            (root / "manifest.json").write_text(json.dumps(manifest))
            with self.assertRaises(MonitoringError):
                verify_manifest(root, {})

    def test_prepositioned_input_allowed_but_orphan_secret_never_overwritten(self):
        import tempfile

        from helpers.lifecycle import check_prepare_directory

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            p = root / "inputs/application-contract.json"
            p.parent.mkdir()
            p.write_text("{}")
            check_prepare_directory(root, p)
            secret = root / "secrets/password"
            secret.parent.mkdir()
            secret.write_text("sentinel")
            with self.assertRaises(MonitoringError):
                check_prepare_directory(root, p)
            self.assertEqual(secret.read_text(), "sentinel")


if __name__ == "__main__":
    unittest.main()
