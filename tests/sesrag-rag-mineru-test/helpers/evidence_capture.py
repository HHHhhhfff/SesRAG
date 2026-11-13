"""严格识别模型请求的独立不可信证据消息，保留来源编号校验。"""

import re

_PREFIX = re.compile(r"^(?:\[S([1-9]\d*)\]\s+)?\[非可信检索证据\]")


def evidence_prefix(text):
    return _PREFIX.match(text) is not None


def source_number(text):
    match = _PREFIX.match(text)
    if match is None or match[1] is None:
        raise ValueError("EVIDENCE_SOURCE_NUMBER_MISSING")
    return int(match[1])


def validate_capture(inputs, *, expect_evidence):
    # 空捕获只有调用方明确允许预算全删时合法；已有输入始终严格验来源编号。
    if expect_evidence and not inputs:
        raise AssertionError("EXPECTED_EVIDENCE_CAPTURE_EMPTY")
    if any(not value for value in inputs):
        raise AssertionError("EVIDENCE_CAPTURE_MESSAGE_EMPTY")
    return [source_number(value) for value in inputs]
