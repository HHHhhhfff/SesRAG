"""MOD_006/QLT_006：在私有进程检查事实字段，仅输出命中计数。"""

import json
import os
from pathlib import Path
from urllib.parse import unquote, urlsplit

import psycopg


def main():
    url = urlsplit(os.environ["DATABASE_URL"])
    secret_values = [
        os.environ["MODEL_API_KEY"],
        os.environ["PROVIDER_CONTROL_TOKEN"],
        unquote(url.password),
        os.environ["DATABASE_URL"],
    ]
    matches = {}
    with psycopg.connect(
        host=url.hostname,
        user=unquote(url.username),
        password=unquote(url.password),
        dbname=url.path.lstrip("/"),
        port=url.port,
    ) as connection:
        for table in [
            "model_profiles",
            "runs",
            "run_events",
            "messages",
            "context_plans",
            "conversation_summaries",
        ]:
            rows = connection.execute(f"SELECT row_to_json(t)::text FROM {table} t").fetchall()
            matches[table] = {
                "rows_scanned": len(rows),
                "rows_with_secret": sum(
                    any(value in row[0] for value in secret_values) for row in rows
                ),
            }
    category = os.environ["WORKSPACE_PROBE_CATEGORY"]
    result = {
        "status": "passed"
        if all(item["rows_with_secret"] == 0 for item in matches.values())
        else "failed",
        "tables": matches,
    }
    Path(f"/outputs/{category}/secret-facts.json").write_text(json.dumps(result))
    print(json.dumps({"status": "passed", "scan_status": result["status"]}))


if __name__ == "__main__":
    main()
