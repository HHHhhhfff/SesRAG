"""任务1工具自检；只检查导入/版本/契约工具，不执行产品用例。"""

import importlib
import json
import sys
from importlib.metadata import version
from pathlib import Path

from jsonschema import Draft202012Validator

sys.stdout.reconfigure(encoding="utf-8")
assert sys.version_info[:2] == (3, 12), "请使用项目.venv中的Python 3.12"
packages = {
    "pytest": "pytest",
    "pytest_asyncio": "pytest-asyncio",
    "ruff": "ruff",
    "mypy": "mypy",
    "httpx": "httpx",
    "httpx2": "httpx2",
    "psycopg": "psycopg",
    "sqlalchemy": "SQLAlchemy",
    "docx": "python-docx",
    "jsonschema": "jsonschema",
    "aiosqlite": "aiosqlite",
    "alembic": "alembic",
    "fastapi": "fastapi",
}
for module, distribution in packages.items():
    importlib.import_module(module)
    print(f"[工具通过] {distribution} {version(distribution)}")

test_root = Path(__file__).resolve().parents[1]
for path in (
    test_root / "specific_test_script/category-result.schema.json",
    test_root.parents[1] / "contracts/run_event_v1.json",
):
    Draft202012Validator.check_schema(json.loads(path.read_text(encoding="utf-8")))
    print(f"[工具通过] JSON Schema可解析：{path.name}")
validator = Draft202012Validator({"type": "object", "required": ["id"]})
assert validator.is_valid({"id": "工具哨兵"})
assert not validator.is_valid({}), "契约工具必须拒绝缺字段，而不是只导入成功"
print("Python工具自检完成；未执行产品测试。")
