"""REAL_009/011：真实生成及成本/未知结果边界；完整链计数暂缓项不伪执行。"""

import tempfile
from pathlib import Path
from uuid import uuid4

from helpers.case_runner import run_category
from helpers.common import write
from helpers.live_budget import LiveBudget
from helpers.live_cases import LiveCase


def real009(c):
    # REAL_009：生成能力可独立真实验证，不伪称四能力全链。
    live = LiveCase(c, {"generation"})
    try:
        models = __import__("json").loads(Path("/config/models.json").read_text())
        model = next(
            r
            for r in models
            if r.get("provider_kind") == "openai_compatible" and r.get("status") == "enabled"
        )
        thread = live.request("POST", "/api/v2/threads", expected=(201,), json={"title": c.case_id})
        live.reserve("answers")
        made = live.request(
            "POST",
            f"/api/v3/threads/{thread['thread_id']}/messages",
            expected=(201,),
            json={
                "content": "请用一句中文说明你已收到这条连通性验证请求。",
                "branch_id": thread["default_branch_id"],
                "expected_version": 0,
                "model_profile_id": model["profile_id"],
                "model_profile_version": model["version"],
                "rag": {"enabled": False},
            },
            headers={"Idempotency-Key": c.case_id + "-" + str(uuid4())},
        )
        live.wait("/api/v3/runs/" + made["run_id"], "status")
        events = live.request("GET", "/api/v3/runs/" + made["run_id"] + "/events")["events"]
        c.check(
            any(r["type"] == "message.completed" for r in events)
            and any(
                r["type"] == "answer.delta" and r["data"].get("text", "").strip() for r in events
            ),
            "真实模型请求产生回答增量及最终消息",
        )
        detail = live.request("GET", "/api/v2/threads/" + thread["thread_id"])
        answers = [
            r
            for r in detail["messages"]
            if r.get("run_id") == made["run_id"] and r["role"] == "assistant"
        ]
        c.check(
            len(answers) == 1 and answers[0]["content"].strip(), "唯一持久assistant及非空真实正文"
        )
        stream = live.client.get("/api/v3/runs/" + made["run_id"] + "/events/stream")
        c.check(
            stream.status_code == 200
            and "answer.delta" in stream.text
            and "run.succeeded" in stream.text,
            "正式SSE携带回答增量及终态",
        )
        c.note(
            "观察",
            {
                "run_id": made["run_id"],
                "model_profile_id": model["profile_id"],
                "version": model["version"],
                "scope": "真实生成；RAG关闭；不作为完整四能力闭环",
            },
        )
    finally:
        live.close()


def real011(c):
    # REAL_011：实际共享账本耗尽后拒绝且不退款；不为验证成本再发付费请求。
    live = LiveCase(c, set())
    try:
        with tempfile.TemporaryDirectory(dir="/data/scratch") as directory:
            plan = Path(directory) / "plan.json"
            write(plan, {"budget": {"cloud_jobs": 1, "timeout_seconds": 60}, "files": []})
            budget = LiveBudget(plan, Path(directory) / "state.sqlite")
            budget.reserve("cloud_jobs")
            c.rejects(lambda: budget.reserve("cloud_jobs"), error_types=(ValueError,))
            c.rejects(lambda: budget.reserve("cloud_jobs", -1), error_types=(ValueError,))
        c.check("cloud_jobs" in live.plan["budget"], "真实本轮共享预算明确")
        # 实际获准输入按hash重验；本例不为预算负例重复发起云作业。
        if "mineru" in c.context.get("real_capabilities", []):
            approved = live.plan.get("files", [])
            c.check(bool(approved), "MinerU计划须含获准原件")
            for item in approved:
                c.check(bool(live.budget.approved_input(item["file"])), "实际获准原件hash仍匹配")
            c.rejects(
                lambda: live.budget.approved_input("/inputs/live/unapproved.docx"),
                error_types=(ValueError,),
            )
        c.note("观察", "未知提交已经预留的逻辑预算不可退款；供应商实际成本不能由本地账本断言为0")
    finally:
        live.close()


CASES = {"REAL_009": real009, "REAL_011": real011}
if __name__ == "__main__":
    raise SystemExit(run_category(CASES))
