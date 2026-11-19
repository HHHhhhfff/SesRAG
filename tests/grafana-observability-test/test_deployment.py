"""持久部署入口安全回归：只使用临时文件，不启动第二套环境。"""

import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "scripts"))
from deployment.configuration import parse_env, parse_prepared_secrets, runtime_defaults, write_env
from deployment.stack import assert_owned, binding_identity, has_database, record_child_result
from helpers.lifecycle import Environment
from helpers.preflight import MonitoringError


class DeploymentTests(unittest.TestCase):
    def test_child_partial_does_not_become_parent_passed(self):
        # DEP-09：下层未运行项必须出现在总报告，不能只保留隐藏的child状态。
        observer = type("Observer", (), {})()
        observer.report = {}
        checks = []
        observer.check = lambda *args: checks.append(args)
        record_child_result(observer, "Verify", "id", "partial")
        self.assertEqual(checks[0][1], "not_run")
        self.assertEqual(observer.report["monitoring_runs"][0]["status"], "partial")

    def test_template_blank_values_get_runtime_defaults(self):
        # DEP-07：模板显式空白不应绕过实际MinerU存储域/端口默认值。
        values = {"MINERU_STORAGE_HOST_ALLOWLIST": "", "SESRAG_API_PORT": ""}
        runtime_defaults(values)
        self.assertEqual(values["SESRAG_API_PORT"], "8000")
        self.assertIn("cdn-mineru.openxlab.org.cn", values["MINERU_STORAGE_HOST_ALLOWLIST"])

    def test_database_volume_requires_backup_even_without_container(self):
        # DEP-08：Destroy后的容器为空，但持久数据库仍必须在Update前备份。
        self.assertTrue(
            has_database({"container": [], "volume": [{"Name": "sesrag-live_postgres_data"}]})
        )
        self.assertFalse(has_database({"container": [], "volume": []}))

    def test_env_roundtrip_and_preservation(self):
        # DEP-01：更新配置不能丢掉密码中的特殊字符或已有自定义字段。
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / ".env"
            values = {"MODEL_API_KEY": "a$b#c", "CUSTOM": "keep"}
            write_env(path, values)
            self.assertEqual(parse_env(path), values)

    def test_duplicate_env_rejected(self):
        # DEP-02：不依赖dotenv最后一条覆盖的隐式语义。
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / ".env"
            path.write_text("A=x\nA=y\n", encoding="utf-8")
            with self.assertRaises(ValueError):
                parse_env(path)

    def test_secret_sections_do_not_reuse_generation_key(self):
        # DEP-03：生成/向量/重排/MinerU凭据独立解析，不能错绑。
        data = "\n".join(
            f"```\n{title}：\n- API Key：{secret}\n"
            "- 模型基地址：https://example.com/v1\n- 模型名字：model\n```"
            for title, secret in [
                ("会话模型", "chat"),
                ("向量化模型", "embed"),
                ("重排模型", "rank"),
                ("MinerU工具", "mineru"),
            ]
        )
        result = parse_prepared_secrets(data)
        self.assertEqual(
            [result[k]["secret"] for k in ("chat", "embedding", "rerank", "mineru")],
            ["chat", "embed", "rank", "mineru"],
        )

    def test_foreign_resource_rejected(self):
        # DEP-04：同名project没有随机owner标记也不能接管/销毁。
        with self.assertRaises(ValueError):
            assert_owned({"com.docker.compose.project": "sesrag-live"}, "owner")
        assert_owned(
            {"com.docker.compose.project": "sesrag-live", "io.sesrag.deployment.owner": "owner"},
            "owner",
        )

    def test_rebind_only_changes_provenance(self):
        # DEP-05：更新源码引用允许，网络或目标改变不属于RefreshBinding。
        before = {"source_ref": "a", "application_network_id": "net", "services": {"api": "api"}}
        after = {**before, "source_ref": "b"}
        self.assertEqual(binding_identity(before), binding_identity(after))
        self.assertNotEqual(
            binding_identity(before), binding_identity({**after, "application_network_id": "other"})
        )

    def test_monitor_rejects_rebind_to_another_network(self):
        # DEP-06：显式刷新也必须拒绝换采集对象；不允许脚本借更新接管网络。
        with tempfile.TemporaryDirectory() as temp:
            env = object.__new__(Environment)
            env.path = Path(temp)
            env.reconcile = lambda: None
            env.check_drift = lambda: None
            env.state = {"contract_hash": "old"}
            old = {"application_network_id": "one"}
            new = {"application_network_id": "two"}
            with (
                patch("helpers.lifecycle.load", return_value=old),
                patch("helpers.lifecycle.validate_contract", return_value=new),
            ):
                with self.assertRaisesRegex(MonitoringError, "OBS005_BINDING_IDENTITY"):
                    env.refresh_binding(Path(temp) / "new.json")


if __name__ == "__main__":
    unittest.main()
