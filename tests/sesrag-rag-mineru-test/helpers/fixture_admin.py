"""专属PG夹具工具：限制数据库身份；不伪造Run/Build成功作为业务证据。"""

import hashlib
import json
import re
from pathlib import Path

from sqlalchemy import create_engine, text
from sqlalchemy.engine import make_url


class FixtureAdmin:
    def __init__(self, private_file="/run/secrets/tools-private.json"):
        private = json.loads(Path(private_file).read_text())
        url = make_url(private["database_url"])
        if (
            url.host != "postgres"
            or url.database != "rag_test"
            or url.username != "rag_test"
            or not private["project"].startswith("sesrag-rag-")
        ):
            raise ValueError("FIXTURE_DATABASE_NOT_OWNED")
        self.private, self.url = private, url

    def database_name(self, case_id):
        if not re.fullmatch(r"[A-Z][A-Z0-9_]{2,60}", case_id):
            raise ValueError("INVALID_CASE_ID")
        return (
            "rag_case_"
            + hashlib.sha256((self.private["run_id"] + case_id).encode()).hexdigest()[:24]
        )

    def create_database(self, case_id):
        name = self.database_name(case_id)
        engine = create_engine(self.url.set(database="postgres"), isolation_level="AUTOCOMMIT")
        try:
            with engine.connect() as conn:
                # 标识符完全由内部hash生成，不接受用户SQL或开发库名。
                conn.execute(text(f'CREATE DATABASE "{name}"'))
        finally:
            engine.dispose()
        return self.url.set(database=name)

    def drop_database(self, case_id):
        name = self.database_name(case_id)
        engine = create_engine(self.url.set(database="postgres"), isolation_level="AUTOCOMMIT")
        try:
            with engine.connect() as conn:
                conn.execute(text(f'DROP DATABASE IF EXISTS "{name}" WITH (FORCE)'))
        finally:
            engine.dispose()

    def vector_inputs(self, count=10000, dimension=384):
        # 返回确定性输入，不登记为端到端模型产物；具体持久化由后续performance用例设计。
        if not 1 <= count <= 20000 or dimension not in {384, 1024}:
            raise ValueError("FIXTURE_SCALE_LIMIT")
        for seq in range(count):
            values = [((seq + 7) * (i + 3) % 997) / 997 + 0.01 for i in range(dimension)]
            yield {"seq": seq, "text": f"合成性能片段 {seq}", "vector": values}
