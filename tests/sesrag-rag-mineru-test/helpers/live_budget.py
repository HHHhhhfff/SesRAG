"""真实分类共用逻辑预算账本；未知提交不能撤销额度或自动再开新工作。"""

import hashlib
import json
import sqlite3
import time
from pathlib import Path


class LiveBudget:
    def __init__(self, plan="/config/live-inputs.json", state="/data/scratch/live-budget.sqlite"):
        self.plan = json.loads(Path(plan).read_text())
        self.state = Path(state)
        self.state.parent.mkdir(parents=True, exist_ok=True)

    def reserve(self, kind, amount=1):
        if (
            kind not in self.plan["budget"]
            or kind in {"timeout_seconds", "max_output_tokens"}
            or type(amount) is not int
            or amount < 1
        ):
            raise ValueError("LIVE_BUDGET_KIND_INVALID")
        db = sqlite3.connect(self.state, timeout=5)
        try:
            db.execute(
                "CREATE TABLE IF NOT EXISTS limits (key TEXT PRIMARY KEY,value REAL NOT NULL)"
            )
            db.execute("BEGIN IMMEDIATE")
            started = db.execute("SELECT value FROM limits WHERE key='started'").fetchone()
            if started is None:
                db.execute("INSERT INTO limits VALUES ('started',?)", (time.time(),))
                started = (time.time(),)
            if time.time() - started[0] > self.plan["budget"]["timeout_seconds"]:
                raise ValueError("LIVE_PLAN_DEADLINE")
            previous = db.execute("SELECT value FROM limits WHERE key=?", (kind,)).fetchone()
            total = (previous[0] if previous else 0) + amount
            if total > self.plan["budget"][kind]:
                raise ValueError("LIVE_PLAN_BUDGET_EXHAUSTED")
            db.execute("INSERT OR REPLACE INTO limits VALUES (?,?)", (kind, total))
            db.commit()
        finally:
            db.close()

    def approved_input(self, path):
        path = Path(path).resolve()
        expected = next((r for r in self.plan["files"] if Path(r["file"]).resolve() == path), None)
        if expected is None or not path.is_relative_to(Path("/inputs/live")):
            raise ValueError("LIVE_INPUT_NOT_APPROVED")
        raw = path.read_bytes()
        if hashlib.sha256(raw).hexdigest() != expected["sha256"]:
            raise ValueError("LIVE_INPUT_CHANGED")
        return raw
