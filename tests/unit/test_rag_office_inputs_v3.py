"""办公容器验证与云端包边界，不冒充真实解析效果测试。"""

import io
from zipfile import ZipFile

import pytest

from backend.application.errors import ApplicationError
from backend.infrastructure.rag.mineru_outputs import normalize_package
from backend.infrastructure.rag.office_validation import validate_source


def package(files):
    stream = io.BytesIO()
    with ZipFile(stream, "w") as archive:
        for key, value in files.items():
            archive.writestr(key, value)
    return stream.getvalue()


def test_office_extension_cannot_hide_text_or_wrong_container():
    for extension in (".doc", ".docx", ".pdf", ".xls", ".xlsx", ".ppt", ".pptx"):
        with pytest.raises(ApplicationError):
            validate_source("file" + extension, "application/octet-stream", b"plain text")
    wrong = package({"[Content_Types].xml": "<Types/>", "xl/workbook.xml": "<workbook/>"})
    with pytest.raises(ApplicationError):
        validate_source("pretend.docx", None, wrong)


@pytest.mark.parametrize("member", ["../full.md", "/full.md", "C:/full.md", "nested.zip"])
def test_malicious_zip_is_rejected_before_normalization(member):
    with pytest.raises(ApplicationError) as error:
        normalize_package(package({"full.md": "body", member: "hostile"}), ".docx")
    assert error.value.code == "ARTIFACT_UNSAFE"


def test_empty_result_fails_and_office_page_does_not_become_source_page():
    with pytest.raises(ApplicationError):
        normalize_package(package({"full.md": " \n"}), ".pdf")
    result = normalize_package(
        package(
            {
                "full.md": "text",
                "a_content_list.json": '[{"type":"text","text":"text","page_idx":2}]',
            }
        ),
        ".docx",
    )
    assert result.blocks[0].locations[0]["origin"] == "normalized"
    result = normalize_package(
        package(
            {
                "full.md": "text",
                "a_content_list.json": '[{"type":"text","text":"text","page_idx":2}]',
            }
        ),
        ".pdf",
    )
    assert result.blocks[0].locations[0]["number"] == 3
