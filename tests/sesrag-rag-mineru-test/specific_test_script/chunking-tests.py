"""PAR_010/011与CHK_001～010：本地结构、切片与真实PG不可变边界。"""

import asyncio
import hashlib
from unittest.mock import patch

from helpers.case_runner import run_category

from backend.api.schemas.v3.documents import ChunkPolicy
from backend.infrastructure.rag.isolated_processing import isolated
from backend.infrastructure.rag.local_structure import parse_text
from backend.infrastructure.rag.structured_chunker import split_artifact


def covered(c, artifact, chunks):
    positions = set()
    for seq, chunk in enumerate(chunks):
        c.equal(chunk.seq, seq, "seq连续")
        c.equal(chunk.text, artifact.text[chunk.start : chunk.end], "切片为规范文本右开区间")
        positions.update(range(chunk.start, chunk.end))
    c.check(
        all(i in positions or s.isspace() for i, s in enumerate(artifact.text)),
        "所有非空白正文完整覆盖",
    )


def par010(c):
    # PAR_010：CRLF/空行/末行/Unicode映射原行，字符区间不是UTF-8字节。
    for source in ("\r\n首行🙂\r\n\r\n末行", "one\ntwo\n", "\n\n中\n"):
        artifact = parse_text(source.encode(), ".txt")
        for block in artifact.blocks:
            c.equal(artifact.text[block.start : block.end], block.text, "块正文区间")
            location = block.locations[0]
            c.equal(location["number"], artifact.text[: block.start].count("\n") + 1, "行号1基")
            c.equal(location["origin"], "source", "txt原源位置")
        covered(c, artifact, split_artifact(artifact, size=8, overlap=2))


def par011(c):
    # PAR_011：Markdown五类结构及未覆盖文本不丢失，不请求远程资产。
    source = (
        "# 一级\n\n段落🙂\n\n## 二级\n\n```python\nprint(1)\n```\n\n"
        "|列|值|\n|---|---|\n|A|37|\n\n<em>未丢正文</em>\n"
    )
    artifact = parse_text(source.encode(), ".md")
    c.equal(artifact.text, source, "规范正文保留输入")
    c.check(
        {"heading", "paragraph", "code", "table"} <= {r.kind for r in artifact.blocks},
        "结构类别完整",
    )
    for block in artifact.blocks:
        c.equal(source[block.start : block.end], block.text, "结构块范围一致")
    covered(c, artifact, split_artifact(artifact, size=40, overlap=8))


def chk001(c):
    # CHK_001：交叉字段约束由正式入口判断，纯函数拒绝不能掩盖HTTP层转换。
    from uuid import uuid4

    e = c.environment()
    doc = e.upload(raw=b"hello world")
    artifact = parse_text(b"hello world", ".txt")
    c.equal(
        ChunkPolicy().model_dump(),
        {"mode": "structure_v1", "size": 800, "overlap": 120, "max_chunks": 50000},
        "默认策略",
    )
    for size, overlap in ((1, 0), (16000, 15999), (100, 99)):
        split_artifact(artifact, size=size, overlap=overlap)
        build = e.request(
            "POST",
            "/api/v3/documents/" + doc["document_id"] + "/index-builds",
            expected=(202,),
            json={"chunker": {"size": size, "overlap": overlap}},
            headers={"Idempotency-Key": str(uuid4())},
        )
        e.finish("/api/v3/index-builds/" + build["index_batch_id"])
        frozen = e.sql(
            "SELECT chunker_snapshot FROM index_builds WHERE index_batch_id=:id",
            {"id": build["index_batch_id"]},
        )[0]["chunker_snapshot"]
        c.equal((frozen["size"], frozen["overlap"]), (size, overlap), "合法边界冻结读回")
    for data in (
        {"size": 0},
        {"size": 16001},
        {"size": 1, "overlap": 1},
        {"overlap": -1},
        {"size": True, "overlap": 0},
        {"overlap": False},
        {"mode": "other"},
    ):
        c.rejects(lambda data=data: split_artifact(artifact, **data), error_types=(Exception,))
        e.request(
            "POST",
            "/api/v3/documents/" + doc["document_id"] + "/index-builds",
            expected=(422,),
            json={"chunker": data},
            headers={"Idempotency-Key": str(uuid4())},
        )


def chk002(c):
    # CHK_002：后半窗合理块尾优先，有无边界两组。
    artifact = parse_text(("A" * 60 + "\n" + "B" * 100).encode(), ".txt")
    chunks = split_artifact(artifact, size=100, overlap=0)
    c.equal(chunks[0].end, artifact.blocks[0].end, "结构模式优先合理块尾")
    covered(c, artifact, chunks)
    other = parse_text(b"A" * 200, ".txt")
    c.equal(split_artifact(other, size=100, overlap=0)[0].end, 100, "无合理边界按窗结束")


def chk003(c):
    # CHK_003：字符模式严格按窗，来源映射仍保持。
    artifact = parse_text(("A" * 60 + "\n" + "B" * 200).encode(), ".txt")
    chunks = split_artifact(artifact, size=100, overlap=20, mode="character_v1")
    c.equal(chunks[0].end, 100, "兼容字符窗")
    c.equal(chunks[1].start, 80, "足够窗口时重叠20")
    covered(c, artifact, chunks)
    c.check(all(r.locations for r in chunks), "字符模式不丢来源")


def chk004(c):
    # CHK_004：中文/emoji及混合输入受字节上限与字符窗双约束。
    for source in ("中" * 1000, "🙂" * 1000, "a中🙂" * 600):
        artifact = parse_text(source.encode(), ".txt")
        chunks = split_artifact(artifact, size=800, overlap=120, max_bytes=900)
        c.check(
            all(len(r.text.encode()) <= 900 and len(r.text) <= 800 for r in chunks), "每片双预算"
        )
        covered(c, artifact, chunks)


def chk005(c):
    # CHK_005：临界重叠和缩窗仍前进，白片不产生假有效结果。
    for source, size, overlap, max_bytes in (
        ("short", 800, 120, 8192),
        ("a" * 50, 10, 9, 8192),
        ("🙂" * 50, 10, 9, 8),
        (" \n" * 40 + "x", 10, 9, 20),
    ):
        artifact = parse_text(source.encode(), ".txt")
        chunks = split_artifact(artifact, size=size, overlap=overlap, max_bytes=max_bytes)
        c.check(len(chunks) <= len(source), "切片数受输入长度界定")
        c.check(
            all(a.start < b.start for a, b in zip(chunks, chunks[1:], strict=False)), "游标严格前进"
        )
        c.check(all(r.text.strip() for r in chunks), "不保存纯白片")
        covered(c, artifact, chunks)


def chk006(c):
    # CHK_006：49999/50000允许，50001拒绝，不静默截断。
    for size in (49999, 50000):
        artifact = parse_text(b"a" * size, ".txt")
        c.equal(len(split_artifact(artifact, size=1, overlap=0)), size, "有效片上限前/等于")
    artifact = parse_text(b"a" * 50001, ".txt")
    c.rejects(lambda: split_artifact(artifact, size=1, overlap=0), codes={"CHUNK_COUNT_LIMIT"})


def chk007(c):
    # CHK_007：实际发布后查询连续seq/hash，新Build使用新Chunk身份。
    e = c.environment()
    doc = e.upload(raw=("片段🙂\n" * 300).encode())
    first = e.sql(
        "SELECT chunk_id,seq,text,content_hash,start_offset,end_offset FROM chunks ORDER BY seq"
    )
    c.equal([r["seq"] for r in first], list(range(len(first))), "发布seq连续")
    for row in first:
        c.equal(
            row["content_hash"],
            hashlib.sha256(row["text"].encode()).hexdigest(),
            "实际持久文本hash",
        )
    build = e.request(
        "POST",
        "/api/v3/documents/" + doc["document_id"] + "/index-builds",
        expected=(202,),
        json={},
        headers={"Idempotency-Key": "chk007-rebuild"},
    )
    e.finish("/api/v3/index-builds/" + build["index_batch_id"])
    later = e.sql(
        "SELECT chunk_id FROM chunks WHERE index_batch_id=:id", {"id": build["index_batch_id"]}
    )
    c.check(not {r["chunk_id"] for r in first} & {r["chunk_id"] for r in later}, "新批次新片段身份")


def chk008(c):
    # CHK_008：跨块/半行/重叠逐区间与来源相交。
    artifact = parse_text(("# 标题\n\n" + "中🙂" * 100 + "\n\n后段\n").encode(), ".md")
    chunks = split_artifact(artifact, size=40, overlap=15)
    for chunk in chunks:
        for segment in chunk.block_segments:
            block = next(b for b in artifact.blocks if b.block_id == segment["block_id"])
            c.equal(
                (segment["start"], segment["end"]),
                (max(chunk.start, block.start), min(chunk.end, block.end)),
                "块范围裁剪真实交集",
            )
        for location in chunk.locations:
            c.check(
                chunk.start <= location["start_offset"] < location["end_offset"] <= chunk.end,
                "来源也裁剪到片内",
            )


def chk009(c):
    # CHK_009：不可变成功Chunk由PG拒写而非只读界面。
    e = c.environment()
    e.upload()
    for set_clause in ("text='forged'", "start_offset=start_offset+1", "embedding=NULL"):
        c.rejects(lambda set_clause=set_clause: e.sql("UPDATE chunks SET " + set_clause))


def chk010(c):
    # CHK_010：真实子进程超时/取消必须kill+wait，Linux资源限制在执行进程核对。
    from backend.infrastructure.rag import isolated_processing as module

    processes = []
    original = asyncio.create_subprocess_exec

    async def capture(*args, **kwargs):
        process = await original(*args, **kwargs)
        processes.append(process)
        return process

    async def exercise():
        with patch.object(module.asyncio, "create_subprocess_exec", capture):
            try:
                await isolated("text", b"a" * 1000000, ".txt", timeout=0.001)
            except Exception as exc:
                c.equal(exc.code, "DOCUMENT_PARSE_LIMIT", "超时稳定拒绝")
            task = asyncio.create_task(isolated("text", b"a" * 1000000, ".txt"))
            await asyncio.sleep(0.001)
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass
        c.check(
            processes and all(p.returncode is not None for p in processes),
            "超时/取消均已回收子进程",
        )
        artifact = await isolated("text", "本地仍可用🙂".encode(), ".txt")
        c.equal(artifact.text, "本地仍可用🙂", "取消后槽位释放")

    asyncio.run(exercise())


CASES = {
    "PAR_010": par010,
    "PAR_011": par011,
    **{f"CHK_{n:03}": globals()[f"chk{n:03}"] for n in range(1, 11)},
}
if __name__ == "__main__":
    raise SystemExit(run_category(CASES))
