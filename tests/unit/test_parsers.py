from pathlib import Path

from backend.infrastructure.rag.parsers import parse_document


def test_parse_markdown_returns_plain_text_and_location(tmp_path: Path):
    path = tmp_path / "note.md"
    path.write_text("# 标题\n\n正文", encoding="utf-8")

    parsed = parse_document(path, ".md")

    assert parsed.text == "# 标题\n\n正文"
    assert parsed.source_name == "note.md"


def test_parse_unsupported_extension_fails():
    try:
        parse_document(Path("unknown.pdf"), ".pdf")
    except ValueError as exc:
        assert "unsupported" in str(exc)
    else:
        raise AssertionError("unsupported extension must fail")
