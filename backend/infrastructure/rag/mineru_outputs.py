"""云端包验证与既定Markdown协议；未知布局不冒充原源位置。"""

import io
import json
import unicodedata
from dataclasses import replace
from pathlib import PurePosixPath
from zipfile import BadZipFile, ZipFile

from markdown_it import MarkdownIt

from backend.application.errors import PermanentTaskError
from backend.infrastructure.rag.cloud_html import normalize_cloud_html
from backend.infrastructure.rag.local_structure import parse_text


def normalize_package(raw: bytes, extension: str):
    try:
        with ZipFile(io.BytesIO(raw)) as archive:
            infos = archive.infolist()
            if len(infos) > 10000 or sum(i.file_size for i in infos) > 256 * 1024**2:
                raise ValueError()
            names = set()
            markdown = []
            content_lists = []
            for info in infos:
                path = info.filename.replace("\\", "/")
                normalized = unicodedata.normalize("NFC", path).casefold()
                if (
                    len(path) > 240
                    or path.startswith("/")
                    or ":" in path
                    or ".." in path.split("/")
                    or normalized in names
                    or info.file_size > 64 * 1024**2
                    or info.file_size > max(1, info.compress_size) * 100
                    or info.flag_bits & 1
                    or (info.external_attr >> 16) & 0o170000 == 0o120000
                    or PurePosixPath(path).suffix.casefold() in {".zip", ".tar", ".gz", ".7z"}
                ):
                    raise ValueError()
                names.add(normalized)
                if PurePosixPath(path).name == "full.md":
                    markdown.append(info)
                if path.endswith("_content_list.json"):
                    content_lists.append(info)
            if len(markdown) != 1:
                raise PermanentTaskError("MINERU_OUTPUT_UNSUPPORTED", "结果缺少唯一full.md")
            content = archive.read(markdown[0])
            if not content.strip():
                raise PermanentTaskError("MINERU_EMPTY_OUTPUT", "云端未返回有效文本")
            try:
                content = normalize_cloud_html(content.decode("utf-8-sig")).encode()
            except UnicodeError:
                raise PermanentTaskError("MINERU_OUTPUT_UNSUPPORTED", "云端文本不是UTF-8") from None
            tokens = MarkdownIt("commonmark", {"html": True}).parse(content.decode())
            # 图片链接和原始HTML不等于可用于文本RAG的正文；不发起OCR或拉取资产。
            if not any(
                token.content.strip()
                for parent in tokens
                for token in (parent.children or [parent])
                if token.type in {"text", "code_inline", "code_block", "fence"}
            ):
                raise PermanentTaskError("MINERU_EMPTY_OUTPUT", "云端未返回可用文本正文")
            artifact = parse_text(content, ".md", source_locations=False)
            # 只对已定义content-list文本与唯一精确匹配赋原PDF页；其他结构保留block_only。
            if (
                extension == ".pdf"
                and len(content_lists) == 1
                and content_lists[0].file_size <= 32 * 1024**2
            ):
                try:
                    entries = json.loads(archive.read(content_lists[0]))
                    if not isinstance(entries, list) or len(entries) > 100000:
                        raise ValueError()
                    pending = [(entries, 0)]
                    nodes = 0
                    while pending:
                        node, depth = pending.pop()
                        nodes += 1
                        if depth > 64 or nodes > 1000000:
                            raise ValueError()
                        if isinstance(node, dict):
                            pending.extend((value, depth + 1) for value in node.values())
                        elif isinstance(node, list):
                            pending.extend((value, depth + 1) for value in node)
                    blocks = []
                    for block in artifact.blocks:
                        matched = [
                            entry
                            for entry in entries
                            if isinstance(entry, dict)
                            and entry.get("type") == "text"
                            and isinstance(entry.get("text"), str)
                            and entry["text"].strip() == block.text.strip()
                            and type(entry.get("page_idx")) is int
                            and entry["page_idx"] >= 0
                        ]
                        locations = block.locations
                        if len(matched) == 1:
                            locations = (
                                {
                                    "kind": "page",
                                    "origin": "source",
                                    "quality": "verified",
                                    "number": matched[0]["page_idx"] + 1,
                                    "start_offset": block.start,
                                    "end_offset": block.end,
                                },
                            )
                        blocks.append(replace(block, locations=locations))
                    artifact = replace(artifact, blocks=tuple(blocks))
                except (ValueError, UnicodeError, RecursionError):
                    artifact = replace(artifact, unsupported=("provider_locations_unavailable",))
            return artifact
    except (ValueError, BadZipFile, KeyError, OSError, RuntimeError):
        raise PermanentTaskError("ARTIFACT_UNSAFE", "解析包无效或超出安全边界") from None
