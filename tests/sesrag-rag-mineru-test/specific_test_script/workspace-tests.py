"""UI_001～018：真实Chromium执行生产Vue组件/store；逐例独立浏览器上下文。"""

import json
import subprocess

from helpers.case_runner import run_category


def browser_case(case):
    # UI_001～UI_018的原子目标由browser-cases.mjs同编号实现；Python仅承接严格报告。
    process = subprocess.run(
        [
            "node",
            "/suite/helpers/browser-cases.mjs",
            "--case",
            case.case_id,
            "--origin",
            case.context["addresses"]["api"],
        ],
        capture_output=True,
        text=True,
        timeout=240,
    )
    if not process.stdout.strip():
        raise RuntimeError("BROWSER_RESULT_MISSING:" + process.stderr[-200:])
    result = json.loads(process.stdout.strip().splitlines()[-1])
    for row in result["observations"]:
        case.note(row["phase"], row["detail"])
    if result.get("harness_error"):
        raise ValueError(result["harness_error"])
    case.check(result["assertions"] > 0, "浏览器执行了具体断言", result["assertions"])
    case.check(
        result["passed"] and process.returncode == 0, result.get("error") or "真实浏览器目标成立"
    )


CASES = {f"UI_{n:03}": browser_case for n in range(1, 19)}
if __name__ == "__main__":
    raise SystemExit(run_category(CASES))
