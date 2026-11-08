import math
import struct

from backend.application.errors import PermanentTaskError


def validate_vector(vector: object, *, dimension: int | None = None) -> list[float]:
    if not isinstance(vector, (list, tuple)):
        raise PermanentTaskError("EMBEDDING_INVALID", "Embedding 格式无效")
    expected = 384 if dimension is None else dimension
    if type(expected) is not int or not 1 <= expected <= 2000 or len(vector) != expected:
        raise PermanentTaskError("EMBEDDING_DIMENSION_MISMATCH", "Embedding 与声明空间维度不符")
    try:
        invalid = any(
            type(value) not in (int, float)
            or not math.isfinite(value)
            or abs(value) > 3.4028234663852886e38
            for value in vector
        )
    except (OverflowError, ValueError):
        invalid = True
    if invalid:
        raise PermanentTaskError("EMBEDDING_INVALID", "Embedding 必须为有限数字")
    # 新空间采用 cosine，零范数向量不能作为合法候选；旧协议的校验口径单独保留。
    if dimension is not None and not any(
        struct.unpack("<f", struct.pack("<f", value))[0] != 0 for value in vector
    ):
        raise PermanentTaskError("EMBEDDING_INVALID", "cosine 不接受零向量")
    return [float(value) for value in vector]


def normalize_l2_float32(vector: object, *, dimension: int) -> list[float]:
    values = validate_vector(vector, dimension=dimension)
    norm = math.hypot(*values)
    normalized = [struct.unpack("<f", struct.pack("<f", value / norm))[0] for value in values]
    # 转为真实存储精度后再检验，query和document遵守同一空间协议。
    return validate_vector(normalized, dimension=dimension)
