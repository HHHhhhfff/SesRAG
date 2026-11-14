"""A09：真实Worker硬杀、租约回收和20秒停机释放后仍消费原来源。"""

import json
import time


def execute(runner, code):
    result = runner.compose("exec", "-T", "probe", "python", "-c", code, timeout=120)
    return json.loads(result.stdout.strip().splitlines()[-1])


def run_restarts(runner):
    original = runner.compose_files
    runner.compose_files = [*original, runner.runtime.parents[1] / "compose/recovery.yaml"]
    records = []
    try:
        runner.compose("up", "-d", "--no-deps", "--force-recreate", "worker")
        for mode in ("hard_kill", "graceful_release"):
            execute(
                runner, "from pathlib import Path; Path('/data/recovery-delay').touch();print('{}')"
            )
            run = execute(
                runner,
                """import sys,json
sys.path.insert(0,'/tests/obs/tooling')
from evidence import client,request
with client() as c:
 t=request(c,'POST','/api/v1/threads',json={'title':'恢复验证'})
 r=request(c,'POST','/api/v1/threads/'+t['thread_id']+'/messages',json={'content':'受控恢复'})
 print(json.dumps(r))
""",
            )
            task = run["task_id"]
            code = """import os,json,time,psycopg
dsn=os.environ['DATABASE_URL'].replace('postgresql+psycopg://','postgresql://')
with psycopg.connect(dsn) as conn:
 for n in range(100):
  query='SELECT state,generation,trace_origin_json FROM tasks WHERE task_id=%s'
  row=conn.execute(query,('%s',)).fetchone()
  if row[0]=='running':break
  time.sleep(.1)
 else:raise AssertionError('未进入running')
 print(json.dumps({'state':row[0],'generation':row[1],'origin':row[2]}))
""" % ("%s", task)
            before = execute(runner, code)
            started = time.monotonic()
            if mode == "hard_kill":
                runner.compose("kill", "-s", "SIGKILL", "worker")
            else:
                runner.compose("stop", "--timeout", "30", "worker", timeout=40)
            execute(
                runner,
                "from pathlib import Path;Path('/data/recovery-delay').unlink(missing_ok=True);"
                "print('{}')",
            )
            runner.compose("up", "-d", "--no-deps", "worker")
            result = execute(
                runner,
                """import sys,json,os,psycopg
sys.path.insert(0,'/tests/obs/tooling')
from evidence import client,wait
with client() as c:wait(c,'/api/v1/runs/%s')
dsn=os.environ['DATABASE_URL'].replace('postgresql+psycopg://','postgresql://')
with psycopg.connect(dsn) as conn:
 query='SELECT generation,trace_origin_json,state FROM tasks WHERE task_id=%%s'
 row=conn.execute(query,('%s',)).fetchone()
print(json.dumps({'generation':row[0],'origin':row[1],'state':row[2]}))
"""
                % (run["run_id"], task),
            )
            assert before["origin"] is not None and before["origin"] == result["origin"]
            assert result["generation"] > before["generation"] and result["state"] == "succeeded"
            records.append(
                dict(
                    mode=mode,
                    generation=result["generation"],
                    source_preserved=True,
                    seconds=time.monotonic() - started,
                )
            )
        runner.results.append(
            dict(
                case="worker-restarts",
                status="passed",
                message="硬杀/停机释放后原来源恢复",
                evidence={"runs": records},
            )
        )
    finally:
        runner.compose_files = original
