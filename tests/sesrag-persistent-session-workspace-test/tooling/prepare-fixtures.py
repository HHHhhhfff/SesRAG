"""生成可重复的合成输入和安全清单，不写入产品数据库。"""

from __future__ import annotations

import argparse
import hashlib
import io
import json
import os
import tempfile
import zipfile
from pathlib import Path
from xml.sax.saxutils import escape

SUITE = Path(__file__).resolve().parents[1]
FIXTURE_VERSION = "workspace-fixtures-v1"


class FixtureError(RuntimeError):
    """公开输出只包含错误码，不包含宿主路径或原始异常。"""


class SafeParser(argparse.ArgumentParser):
    def error(self, _message):
        raise FixtureError("ARGUMENTS_INVALID")


def checked_output(path):
    candidate = Path(path).absolute()
    if candidate == Path(candidate.anchor):
        raise FixtureError("OUTPUT_PATH_REJECTED")
    # 先检查原始路径各层，再resolve，避免符号链接被规范化隐藏。
    if any(part.is_symlink() for part in (candidate, *candidate.parents)):
        raise FixtureError("OUTPUT_PATH_REJECTED")
    return candidate.resolve()


def atomic_write(path, content):
    path = checked_output(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists() and not path.is_file():
        raise FixtureError("OUTPUT_PATH_REJECTED")
    descriptor, temporary = tempfile.mkstemp(prefix=".fixture-", dir=path.parent)
    try:
        with os.fdopen(descriptor, "wb") as stream:
            stream.write(content)
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def minimal_docx(text):
    paragraphs = "".join(
        f'<w:p><w:r><w:t xml:space="preserve">{escape(line)}</w:t></w:r></w:p>'
        for line in text.splitlines()
    )
    parts = {
        "[Content_Types].xml": (
            '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
            '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">'
            '<Default Extension="rels" '
            'ContentType="application/vnd.openxmlformats-package.relationships+xml"/>'
            '<Default Extension="xml" ContentType="application/xml"/>'
            '<Override PartName="/word/document.xml" '
            'ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml"/>'
            "</Types>"
        ),
        "_rels/.rels": (
            '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
            '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
            '<Relationship Id="rId1" '
            'Type="http://schemas.openxmlformats.org/officeDocument/2006/'
            'relationships/officeDocument" '
            'Target="word/document.xml"/></Relationships>'
        ),
        "word/document.xml": (
            '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
            '<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">'
            f"<w:body>{paragraphs}<w:sectPr/></w:body></w:document>"
        ),
    }
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", compression=zipfile.ZIP_STORED) as archive:
        for name, content in parts.items():
            # ZIP固定时间戳和权限，重复执行不因宿主时间改变hash。
            info = zipfile.ZipInfo(name, date_time=(1980, 1, 1, 0, 0, 0))
            info.external_attr = 0o600 << 16
            archive.writestr(info, content.encode("utf-8"))
    return buffer.getvalue()


def prepare_fixtures(output):
    from backend.infrastructure.providers.context_counter import (
        MockTokenCounter,
        token_counter_from_profile,
    )

    output = checked_output(output)
    profiles = json.loads((SUITE / "fixtures/model-profiles.json").read_text(encoding="utf-8"))
    profile = next(item for item in profiles if item["profile_id"] == "ws-http-a")
    counter = token_counter_from_profile(profile)
    mock_counter = MockTokenCounter()
    history = "".join(
        f"L{line:04d} WS_HISTORY_{line:04d} 合成历史片段，编号固定且不代表用户事实。 "
        "The cobalt observatory records a synthetic signal; no personal data or credentials.\n"
        for line in range(1, 1025)
    )
    markdown = (
        "# WS_MARKDOWN_SYNTHETIC_V1\n\n普通文字与 **加粗**、`code`、列表和引用。\n\n"
        "> synthetic quote\n\n- item one\n- item two\n\n"
        "[safe fragment](#ws-markdown-synthetic-v1)\n\n"
        "<script>window.WS_XSS_SENTINEL='script'</script>\n"
        '<img src="x" onerror="window.WS_XSS_SENTINEL=\'image\'">\n'
        "[unsafe link](javascript:window.WS_XSS_SENTINEL='link')\n"
        "<svg onload=\"window.WS_XSS_SENTINEL='svg'\"></svg>\n"
        "```html\n<script>literal code fixture</script>\n```\n"
    )
    docx_text = (
        "WS_DOCX_SYNTHETIC_V1\n最小合法文档素材，仅供后续正式上传路径使用。\n"
        "Stable evidence line 0001."
    )
    files = (
        ("history-long.txt", "text/plain", history, history.encode("utf-8")),
        ("markdown-xss.md", "text/markdown", markdown, markdown.encode("utf-8")),
        (
            "minimal.docx",
            "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            docx_text,
            minimal_docx(docx_text),
        ),
    )
    manifest = {
        "schema_version": 1,
        "fixture_version": FIXTURE_VERSION,
        "encoding_name": "cl100k_base",
        "counter_version": counter.version,
        "business_facts_created": False,
        "files": [],
    }
    output.mkdir(parents=True, exist_ok=True)
    for name, media_type, text, content in files:
        atomic_write(output / name, content)
        manifest["files"].append(
            {
                "name": name,
                "media_type": media_type,
                "bytes": len(content),
                "sha256": hashlib.sha256(content).hexdigest(),
                "text_sha256": hashlib.sha256(text.encode("utf-8")).hexdigest(),
                "text_characters": len(text),
                "token_count": counter.count_text(text),
                "mock_token_count": mock_counter.count_text(text),
            }
        )
    return manifest


def main(argv=None):
    try:
        parser = SafeParser(description=__doc__)
        parser.add_argument("--output", required=True)
        parser.add_argument("--manifest")
        args = parser.parse_args(argv)
        manifest = prepare_fixtures(args.output)
        if args.manifest:
            atomic_write(
                Path(args.manifest),
                (json.dumps(manifest, ensure_ascii=True, sort_keys=True) + "\n").encode("utf-8"),
            )
        result = {"status": "passed", **manifest}
        code = 0
    except Exception as error:
        result = {
            "schema_version": 1,
            "status": "failed",
            "code": str(error) if isinstance(error, FixtureError) else "FIXTURE_PREPARATION_FAILED",
        }
        code = 2
    print(json.dumps(result, ensure_ascii=True, sort_keys=True))
    return code


if __name__ == "__main__":
    raise SystemExit(main())
