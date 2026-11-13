"""分类接入与证据验证；退出0不能替代完整结果。"""

from pathlib import Path

from helpers.common import SUITE, digest, load, schema_check

LOCAL = (
    "catalog ingestion mineru chunking vectors retrieval execution workspace "
    "compatibility lifecycle performance quality"
).split()
REAL = ["real-formats", "real-business", "real-evaluation"]


def manifest():
    value = load(SUITE / "manifest.json")
    schema_check("manifest", value)
    entries = value["categories"]
    if {r["category"] for r in entries} != set(LOCAL + REAL) or len(entries) != 15:
        raise ValueError("MANIFEST_CATEGORY_MISMATCH")
    seen = set()
    for row in entries:
        if row["lane"] != ("real" if row["category"] in REAL else "local"):
            raise ValueError("MANIFEST_LANE_MISMATCH")
        if row["may_charge"] != (row["lane"] == "real"):
            raise ValueError("MANIFEST_CHARGE_MISMATCH")
        entry = (SUITE / row["entrypoint"]).resolve()
        if entry.parent != (SUITE / "specific_test_script").resolve():
            raise ValueError("UNSAFE_ENTRYPOINT")
        ids = [case["case_id"] for case in row["cases"]]
        if len(ids) != len(set(ids)) or seen.intersection(ids):
            raise ValueError("DUPLICATE_CASE_ID")
        seen.update(ids)
        if row["status"] == "ready" and (not ids or not entry.is_file()):
            raise ValueError("READY_WITHOUT_CASE_OR_FILE")
    return {row["category"]: row for row in entries}


def validate_result(value, context, entry, report_root):
    schema_check("result", value)
    for key in ("run_id", "category", "lane"):
        if value[key] != context[key]:
            raise ValueError("RESULT_IDENTITY_MISMATCH")
    cases = value["cases"]
    expected = {c["case_id"]: c for c in entry["cases"]}
    actual = [c["case_id"] for c in cases]
    if set(actual) != set(expected) or len(actual) != len(expected):
        raise ValueError("RESULT_CASE_COVERAGE_MISMATCH")
    for case in cases:
        declared = expected[case["case_id"]]
        for field in ("requirements", "test_points"):
            if set(case[field]) != set(declared[field]):
                raise ValueError("RESULT_REQUIREMENT_MISMATCH")
        for evidence in case["evidence"]:
            relative = Path(evidence["path"])
            path = (report_root / relative).resolve()
            if relative.is_absolute() or not path.is_relative_to(report_root.resolve()):
                raise ValueError("EVIDENCE_PATH_ESCAPE")
            if not path.is_file() or path.stat().st_size > 20 * 1024**2:
                raise ValueError("EVIDENCE_MISSING_OR_TOO_LARGE")
            if digest(path.read_bytes()) != evidence["sha256"]:
                raise ValueError("EVIDENCE_MISSING_OR_CHANGED")
    return [case["status"] for case in cases]
