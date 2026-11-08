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
