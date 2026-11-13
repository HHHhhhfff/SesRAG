"""逐例中文执行与证据；失败不截断同分类后续用例，不允许零断言假通过。"""

import argparse
import json
import time
from pathlib import Path

from helpers.common import SUITE, digest, load, schema_check, write
from helpers.evidence import redact


class Blocked(Exception):
    pass


class Case:
    def __init__(self, spec, context, report):
        self.spec, self.context, self.report = spec, context, Path(report)
        self.case_id = spec["case_id"]
        self.observations = []
        self.assertions = 0
        self.env = None

    def note(self, phase, detail):
        # 数组、集合、时间等观察值先转安全JSON，再落盘；采证不能中断后续用例。
        safe = json.loads(redact(json.dumps(detail, ensure_ascii=False, default=str)))
        row = {"阶段": phase, "信息": safe}
        self.observations.append(row)
        print(f"[{self.case_id}] {phase}：{redact(str(detail))[:500]}", flush=True)

    def check(self, condition, goal, observed=None):
        self.assertions += 1
        self.note("观察", {"断言": goal, "成立": bool(condition), "实际": observed})
        if not condition:
            raise AssertionError(goal)

    def equal(self, actual, expected, goal):
        self.check(actual == expected, goal, {"实际": actual, "预期": expected})

    def rejects(self, operation, *, codes=None, error_types=(Exception,)):
        try:
            operation()
        except error_types as exc:
            code = getattr(exc, "code", type(exc).__name__)
            self.check(codes is None or code in codes, "拒绝原因与约定一致", code)
            return exc
        self.check(False, "非法输入必须被拒绝")

    def environment(self, **settings):
        from helpers.case_environment import CaseEnvironment

        if self.env is not None:
            raise ValueError("CASE_ENVIRONMENT_ALREADY_OPEN")
        self.env = CaseEnvironment(self, **settings)
        self.env.__enter__()
        return self.env

    def block(self, reason):
        raise Blocked(reason)

    def close(self):
        if self.env:
            self.env.__exit__(None, None, None)


def run_category(functions):
    from helpers.case_environment import cleanup_template

    try:
        return _run_category(functions)
    finally:
        # 即使覆盖校核、报告写入或Schema校验失败，也释放分类模板库。
        cleanup_template()


def _run_category(functions):
    parser = argparse.ArgumentParser()
    parser.add_argument("--context", required=True)
    parser.add_argument("--result", required=True)
    args = parser.parse_args()
    context, output = load(args.context), Path(args.result)
    schema_check("context", context)
    if context["lane"] == "local":
        from harness.local_entry import install

        install()
    catalog = load(SUITE / "fixtures/case-catalog.json")["cases"]

    # B/D 是明确暂不可完整验证的真实计数/评测数据项；它们不能被本地分类脚本
    # 伪装成已实现。L/K（以及真实脚本单独处理的 R）才进入分类执行清单。
    def is_verifiable(spec):
        status = str(spec.get("status", ""))
        return all(token not in status for token in ("·B", "·D", "暂不可验证"))

    specs = [r for r in catalog if r["category"] == context["category"] and is_verifiable(r)]
    if set(functions) != {r["case_id"] for r in specs}:
        raise ValueError("CASE_IMPLEMENTATION_COVERAGE_MISMATCH")
    results = []
    for spec in specs:
        case = Case(spec, context, output.parent)
        start = time.monotonic()
        status, error, actual = "passed", None, "全部数据组及断言成立"
        case.note("准备", spec["title"])
        case.note("执行", spec["steps"])
        try:
            functions[spec["case_id"]](case)
            if case.assertions == 0:
                raise ValueError("CASE_WITHOUT_ASSERTIONS")
        except Blocked as exc:
            status, error, actual = "blocked", "PREREQUISITE_UNAVAILABLE", str(exc)
        except AssertionError as exc:
            status, error, actual = "failed", "ASSERTION_FAILED", str(exc)
        except Exception as exc:
            # 公开错误只留安全码；完整库异常可能带SQL/DSN，不直接归档堆栈。
            from backend.application.errors import ApplicationError

            status = "failed" if isinstance(exc, ApplicationError) else "harness_error"
            error = getattr(exc, "code", type(exc).__name__)
            actual = "准备或执行异常：" + error
            if isinstance(exc, (KeyError, AttributeError, TypeError, ValueError)):
                actual += "；" + redact(str(exc))[:300]
            from sqlalchemy.exc import DBAPIError

            if isinstance(exc, DBAPIError):
                # 只记录数据库稳定诊断，不输出SQL参数或包含密码的连接字符串。
                actual += "；SQLSTATE=" + str(getattr(exc.orig, "sqlstate", "unknown"))
                diag = getattr(exc.orig, "diag", None)
                if diag:
                    actual += "；" + redact(str(getattr(diag, "message_primary", "")))[:200]
        finally:
            try:
                case.close()
            except Exception as exc:
                status, error, actual = "harness_error", "CASE_CLEANUP_FAILED", type(exc).__name__
        case.note("结论", {"状态": status, "说明": actual, "断言数": case.assertions})
        proof = output.parent / (spec["case_id"] + ".json")
        write(
            proof,
            {
                "case_id": spec["case_id"],
                "run_id": context["run_id"],
                "lane": context["lane"],
                "observations": case.observations,
                "assertions": case.assertions,
                "status": status,
            },
        )
        results.append(
            {
                **{k: spec[k] for k in ("case_id", "title", "requirements", "test_points")},
                "status": status,
                "duration_ms": (time.monotonic() - start) * 1000,
                "error_code": error,
                "expected": spec["expected"],
                "actual": redact(actual),
                "phases": ["准备", "执行", "观察", "结论"],
                "evidence": [{"path": proof.name, "sha256": digest(proof.read_bytes())}],
            }
        )
        write(
            output,
            {
                "schema_version": 1,
                **{k: context[k] for k in ("run_id", "category", "lane")},
                "cases": results,
            },
        )
    value = load(output)
    schema_check("result", value)
    return (
        2
        if any(r["status"] == "harness_error" for r in results)
        else 1
        if any(r["status"] == "failed" for r in results)
        else 3
        if any(r["status"] != "passed" for r in results)
        else 0
    )
