import math

from backend.application.errors import PermanentTaskError


def validate_vector(vector: object) -> list[float]:
    if not isinstance(vector, (list, tuple)):
        raise PermanentTaskError("EMBEDDING_INVALID", "Embedding 格式无效")
    if len(vector) != 384:
        raise PermanentTaskError("EMBEDDING_DIMENSION_MISMATCH", "Embedding 维度必须为 384")
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
    return [float(value) for value in vector]
