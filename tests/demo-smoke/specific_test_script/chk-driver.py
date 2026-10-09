"""CHK_001/CHK_002：按参数调用真实字符切分函数，不复制实现。"""

import dataclasses
import json

from backend.infrastructure.rag.chunker import chunk_text

result = {"valid": [], "invalid": []}
# CHK_001：边界长度、中文和重叠参数各自保留实际块。
for text in ("中", "中文AB", "中文ABCD🙂E", "中文ABCD🙂EFG"):
    for overlap in (0, 1):
        result["valid"].append(
            {
                "text": text,
                "size": 4,
                "overlap": overlap,
                "chunks": [
                    dataclasses.asdict(draft)
                    for draft in chunk_text(text, chunk_size=4, overlap=overlap)
                ],
            }
        )
result["empty"] = [dataclasses.asdict(draft) for draft in chunk_text("")]
# CHK_002：非法参数必须ValueError，不通过自行替换切分函数制造拒绝。
for size, overlap in ((0, 0), (-1, 0), (4, -1), (4, 4), (4, 5)):
    try:
        chunk_text("非法参数安全输入", chunk_size=size, overlap=overlap)
        error = None
    except Exception as exc:
        error = type(exc).__name__
    result["invalid"].append({"size": size, "overlap": overlap, "error": error})
print("SMOKE_JSON:" + json.dumps(result, ensure_ascii=False))
