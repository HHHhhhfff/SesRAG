"""真实XLS/XLSX产物使用HTML表格，不能把标签当作唯一段落。"""

import io
from zipfile import ZipFile

import pytest

from backend.application.errors import ApplicationError
from backend.infrastructure.rag.mineru_outputs import normalize_package


def test_cloud_html_table_becomes_bounded_text_structure_without_assets():
    stream = io.BytesIO()
    with ZipFile(stream, "w") as archive:
        archive.writestr(
            "full.md",
            "<table><tr><th>Topic</th><th>Value</th></tr><tr><td>Database</td>"
            '<td><p>PostgreSQL</p><img src="https://private.invalid/a">'
            "<script>bad()</script></td></tr></table>",
        )
    artifact = normalize_package(stream.getvalue(), ".xlsx")
    assert "PostgreSQL" in artifact.text
    assert (
        "<table" not in artifact.text
        and "private.invalid" not in artifact.text
        and "bad()" not in artifact.text
    )
    assert artifact.blocks[0].kind == "table"
    assert artifact.blocks[0].locations[0]["quality"] == "block_only"


def test_image_only_cloud_output_is_not_valid_rag_text():
    stream = io.BytesIO()
    with ZipFile(stream, "w") as archive:
        archive.writestr("full.md", "![](images/scan.png)\n\n<img src='private.png'>")
    with pytest.raises(ApplicationError) as failure:
        normalize_package(stream.getvalue(), ".pdf")
    assert failure.value.code == "MINERU_EMPTY_OUTPUT"


@pytest.mark.parametrize(
    "danger",
    [
        "<script>POISON</script>",
        "<style>POISON</style>",
        '<iframe src="https://private.invalid">POISON</iframe>',
        '<object data="https://private.invalid">POISON</object>',
        '<svg onload="POISON"><text>POISON</text></svg>',
        "<script>POISON",
    ],
)
def test_cloud_raw_html_danger_is_removed_before_offsets(danger):
    stream = io.BytesIO()
    with ZipFile(stream, "w") as archive:
        archive.writestr("full.md", "正文\n\n" + danger)
    artifact = normalize_package(stream.getvalue(), ".pdf")
    assert "正文" in artifact.text
    assert "POISON" not in artifact.text
    assert "private.invalid" not in artifact.text
    assert all(artifact.text[b.start : b.end] == b.text for b in artifact.blocks)


def test_cloud_sanitizer_preserves_code_examples_but_removes_raw_assets():
    stream = io.BytesIO()
    with ZipFile(stream, "w") as archive:
        archive.writestr(
            "full.md",
            """正文 <b onclick="POISON">正常值</b>

```html
<script>example()</script>
<table><tr><td>code table</td></tr></table>
```

`<img src="example.png">`

<img src="https://private.invalid" onerror="POISON">

<table><tr><td>ALPHA</td><td>37<svg>POISON</svg></td></tr></table>
""",
        )
    artifact = normalize_package(stream.getvalue(), ".xlsx")
    assert "<script>example()</script>" in artifact.text
    assert "<table><tr><td>code table</td></tr></table>" in artifact.text
    assert '`<img src="example.png">`' in artifact.text
    assert "正常值" in artifact.text and "ALPHA" in artifact.text and "37" in artifact.text
    assert "POISON" not in artifact.text and "private.invalid" not in artifact.text


def test_unmatched_inline_backtick_cannot_overlap_fenced_code_protection():
    code = "```html\n<script>example()</script>\n`literal`\n```\n"
    stream = io.BytesIO()
    with ZipFile(stream, "w") as archive:
        archive.writestr("full.md", "` unmatched\n\n" + code + "\nBody\n<script>POISON</script>")
    artifact = normalize_package(stream.getvalue(), ".pdf")
    assert code in artifact.text
    assert "SES_RAG_CODE_" not in artifact.text
    assert "POISON" not in artifact.text


@pytest.mark.parametrize(
    "body",
    [
        "<div>\n`<script>POISON</script>`\n</div>",
        r"Body \`<script>POISON</script>\`",
    ],
)
def test_non_code_backticks_cannot_hide_raw_html(body):
    stream = io.BytesIO()
    with ZipFile(stream, "w") as archive:
        archive.writestr("full.md", "Body\n\n" + body)
    artifact = normalize_package(stream.getvalue(), ".pdf")
    assert "POISON" not in artifact.text
    assert "<script>" not in artifact.text
    assert "SES_RAG_CODE_" not in artifact.text


@pytest.mark.parametrize("prefix", ["", "Body "])
def test_html_table_backticks_keep_cell_pipe_escaped(prefix):
    stream = io.BytesIO()
    with ZipFile(stream, "w") as archive:
        archive.writestr("full.md", prefix + "<table><tr><td>`x|y`</td><td>37</td></tr></table>")
    artifact = normalize_package(stream.getvalue(), ".xlsx")
    assert r"| `x\|y` | 37 |" in artifact.text
    assert any(b.kind == "table" for b in artifact.blocks)
