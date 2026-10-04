from backend.domain.entities import ChunkDraft


def chunk_text(text: str, *, chunk_size: int = 800, overlap: int = 120) -> list[ChunkDraft]:
    """按字符切分文本，并保留可用于引用的原始 offset。"""
    if chunk_size <= 0:
        raise ValueError("chunk_size must be positive")
    if overlap < 0 or overlap >= chunk_size:
        raise ValueError("overlap must be non-negative and smaller than chunk_size")
    if not text:
        return []

    step = chunk_size - overlap
    chunks: list[ChunkDraft] = []
    start = 0
    seq = 0
    while start < len(text):
        end = min(start + chunk_size, len(text))
        chunks.append(ChunkDraft(seq=seq, text=text[start:end], start_offset=start, end_offset=end))
        seq += 1
        if end == len(text):
            break
        start += step
    return chunks
