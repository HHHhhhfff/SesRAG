"""本地文本结构和云端 Markdown 的规范化；不访问网络或执行代码。"""

from uuid import uuid4

from markdown_it import MarkdownIt

from backend.application.errors import PermanentTaskError
from backend.domain.rag import NormalizedArtifact, ParsedBlock


def parse_text(content: bytes, extension: str, *, source_locations: bool = True):
    if extension not in {".txt", ".md"}:
        raise PermanentTaskError("INVALID_PARSE_SELECTION", "本地解析仅接受 txt/md")
    if len(content) > (10 if source_locations else 32) * 1024 * 1024:
        raise PermanentTaskError("DOCUMENT_PARSE_LIMIT", "文本超过解析上限")
    try:
        text = content.decode("utf-8-sig")
    except UnicodeError:
        raise PermanentTaskError("DOCUMENT_ENCODING_INVALID", "文本必须为 UTF-8") from None
    if not text.strip():
        raise PermanentTaskError("EMPTY_DOCUMENT", "文档没有有效文本")
    if "\x00" in text or any(ord(c) < 32 and c not in "\t\r\n" for c in text):
        raise PermanentTaskError("SOURCE_UNSAFE", "文本包含不支持的控制字符")
    lines = text.splitlines(keepends=True)
    offsets = [0]
    for line in lines:
        offsets.append(offsets[-1] + len(line))
    spans: list[tuple[int, int, str, int]] = []
    levels = {}
    if extension == ".md":
        parser = MarkdownIt("commonmark", {"html": False, "maxNesting": 32}).enable("table")
        for token in parser.parse(text):
            if token.map and token.type in {
                "heading_open",
                "paragraph_open",
                "fence",
                "code_block",
                "table_open",
                "html_block",
                "hr",
            }:
                start_line, end_line = token.map
                # table 内 paragraph 的重复覆盖不作为第二份正文。
                if spans and offsets[start_line] < spans[-1][1]:
                    continue
                kind = {
                    "heading_open": "heading",
                    "paragraph_open": "paragraph",
                    "fence": "code",
                    "code_block": "code",
                    "table_open": "table",
                }.get(token.type, "text")
                if kind == "heading":
                    levels[offsets[start_line]] = len(token.markup)
                spans.append((offsets[start_line], offsets[end_line], kind, start_line + 1))
    else:
        start = 0
        for number, line in enumerate(lines, 1):
            if line.strip():
                spans.append((start, start + len(line), "paragraph", number))
            start += len(line)
    # 未被 AST 覆盖的字符也保留，避免复杂 Markdown 被静默丢弃。
    completed = []
    cursor = 0
    for start, end, kind, number in spans:
        if start > cursor and text[cursor:start].strip():
            completed.append((cursor, start, "text", text[:cursor].count("\n") + 1))
        completed.append((start, end, kind, number))
        cursor = end
    if cursor < len(text) and text[cursor:].strip():
        completed.append((cursor, len(text), "text", text[:cursor].count("\n") + 1))
    blocks = []
    headings: list[str] = []
    heading_levels: list[int] = []
    for start, end, kind, number in completed:
        identity = str(uuid4())
        if kind == "heading":
            level = levels.get(start, 1)
            while heading_levels and heading_levels[-1] >= level:
                heading_levels.pop()
                headings.pop()
            headings.append(text[start:end].lstrip("# ").strip()[:200])
            heading_levels.append(level)
        location = (
            {
                "kind": "line",
                "origin": "source",
                "quality": "verified",
                "number": number,
                "end_number": number + text[start:end].rstrip("\r\n").count("\n"),
                "start_offset": start,
                "end_offset": end,
            }
            if source_locations
            else {
                "kind": "block",
                "origin": "normalized",
                "quality": "block_only",
                "block_id": identity,
                "start_offset": start,
                "end_offset": end,
            }
        )
        blocks.append(
            ParsedBlock(identity, kind, text[start:end], start, end, tuple(headings), (location,))
        )
    if len(blocks) > 100000:
        raise PermanentTaskError("DOCUMENT_PARSE_LIMIT", "结构块超过上限")
    return NormalizedArtifact(
        text,
        tuple(blocks),
        "local_structure_v1" if source_locations else "mineru_cloud_v4_office_text_v1",
    )
