"""容器内逐组执行；失败报告不阻断其他独立组。"""

import argparse
import importlib
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / "tooling"), str(ROOT / "specific_test_script")]
from evidence import outcome  # noqa: E402


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("group")
    args = parser.parse_args()
    group = args.group.lower()
    result = outcome(group, importlib.import_module("test_" + group).run)
    Path("/data/" + group + "-result.json").write_text(json.dumps(result, ensure_ascii=False))
    raise SystemExit(0 if result["status"] == "passed" else 1)


if __name__ == "__main__":
    main()
