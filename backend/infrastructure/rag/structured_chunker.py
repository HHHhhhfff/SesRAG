"""有界结构切片；规范文本范围与原源位置分别保存。"""

from bisect import bisect_left, bisect_right

from backend.application.errors import PermanentTaskError
from backend.application.source_locations import clip_locations
from backend.domain.rag import ChunkDraftV2, NormalizedArtifact


def split_artifact(
    artifact: NormalizedArtifact, *, size=800, overlap=120, max_bytes=8192, mode="structure_v1"
):
    if not (
        type(size) is int and 1 <= size <= 16000 and type(overlap) is int and 0 <= overlap < size
    ):
        raise PermanentTaskError("INVALID_CHUNK_POLICY", "切片大小或重叠无效")
    if type(max_bytes) is not int or max_bytes < 4:
        raise PermanentTaskError("INVALID_CHUNK_POLICY", "模型输入预算过小")
    if mode not in {"structure_v1", "character_v1"}:
        raise PermanentTaskError("INVALID_CHUNK_POLICY", "切片策略不受支持")
    text = artifact.text
    boundaries = sorted({block.end for block in artifact.blocks})
    starts = [block.start for block in artifact.blocks]
    ends = [block.end for block in artifact.blocks]
    chunks: list[ChunkDraftV2] = []
    start = 0
    while start < len(text):
        end = min(len(text), start + size)
        # 尽可能在结构边界结束，但不产生只含少数字符的碎片。
        fitting = boundaries[
            bisect_left(boundaries, start + size // 2) : bisect_right(boundaries, end)
        ]
        if fitting and mode == "structure_v1":
            end = fitting[-1]
        while len(text[start:end].encode()) > max_bytes:
            end = start + max(1, (end - start) // 2)
        if end <= start:
            raise PermanentTaskError("EMBEDDING_INPUT_LIMIT", "无法在预算内切片")
        if text[start:end].strip():
            blocks = artifact.blocks[bisect_right(ends, start) : bisect_left(starts, end)]
            chunks.append(
                ChunkDraftV2(
                    len(chunks),
                    text[start:end],
                    start,
                    end,
                    tuple(
                        {
                            "block_id": b.block_id,
                            "start": max(start, b.start),
                            "end": min(end, b.end),
                        }
                        for b in blocks
                    ),
                    tuple(
                        clip_locations([p for b in blocks for p in b.locations], start, end, text)
                    ),
                )
            )
        if len(chunks) > 50000:
            raise PermanentTaskError("CHUNK_COUNT_LIMIT", "构建超过切片数量上限")
        if end == len(text):
            break
        start = max(start + 1, end - min(overlap, (end - start) // 2))
    return tuple(chunks)
