"""共用只读虚假身份声明；不是用户导入或业务状态seed。"""

import re
from pathlib import Path

from helpers.common import SUITE, load


def baseline(path=None):
    value = load(Path(path) if path else SUITE / "fixtures/baseline.json")
    if (
        value.get("schema_version") != 1
        or value.get("seed_sql_required") is not False
        or value.get("owner") == value.get("other_owner")
        or any(
            not re.fullmatch(r"rag-test-owner-[a-z]", value.get(k, ""))
            for k in ("owner", "other_owner")
        )
    ):
        raise ValueError("BASELINE_IDENTITY_INVALID")
    for key in ("default_embedding", "default_retrieval"):
        row = value.get(key, {})
        if not row.get("profile_id") or type(row.get("version")) is not int or row["version"] < 1:
            raise ValueError("BASELINE_PROFILE_INVALID")
    return value
