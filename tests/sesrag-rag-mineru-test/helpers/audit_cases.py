"""任务3～4覆盖门禁：正式设计→manifest→函数注册；不冒充产品执行结果。"""

import importlib.util
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from helpers.common import SUITE, load
from helpers.protocol import manifest


def main():
    catalog = load(SUITE / "fixtures/case-catalog.json")["cases"]
    ids = [r["case_id"] for r in catalog]
    if len(ids) != 248 or len(set(ids)) != 248:
        raise ValueError("CATALOG_IDENTITY_MISMATCH")
    expected = {r["case_id"]: r for r in catalog if not any(v in r["status"] for v in ("·B", "·D"))}
    entries = manifest()
    seen = set()
    for name, row in entries.items():
        if row["status"] != "ready":
            continue
        spec = importlib.util.spec_from_file_location(
            "case_audit_" + name.replace("-", "_"), SUITE / row["entrypoint"]
        )
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        registered = set(module.CASES)
        declared = {r["case_id"] for r in row["cases"]}
        required = {identity for identity, spec in expected.items() if spec["category"] == name}
        if registered != declared or declared != required:
            raise ValueError("CASE_MAPPING_MISMATCH:" + name)
        for case in row["cases"]:
            for field in ("requirements", "test_points"):
                if set(case[field]) != set(expected[case["case_id"]][field]):
                    raise ValueError("TRACEABILITY_MISMATCH:" + case["case_id"])
        seen.update(registered)
        print(f"{name}：{len(registered)}例函数注册/正式用例/manifest一致")
    engineering = {r["case_id"] for r in catalog if r["category"] == "environment"}
    if seen | engineering != set(expected) or len(engineering) != 10:
        raise ValueError("VERIFIABLE_CASE_MISSING")
    text = (SUITE / "test-cases.md").read_text(encoding="utf8")
    for identity in ids:
        if identity not in text:
            raise ValueError("DOCUMENT_CASE_MISSING")
    print(f"覆盖审计通过：248设计；{len(seen)}分类函数＋10环境用例＝240可验证；8暂缓未冒报ready。")


if __name__ == "__main__":
    main()
