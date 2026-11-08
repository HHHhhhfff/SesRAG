"""PRD-003：本地结构／长块预算与原源位置不混淆。"""

import pytest

from backend.application.errors import ApplicationError
from backend.infrastructure.rag.local_structure import parse_text
from backend.infrastructure.rag.structured_chunker import split_artifact


def test_markdown_structure_preserves_source_and_does_not_fetch_assets():
    source = "# 标题\n\n正文与[链接](https://invalid.example/)\n\n```python\nprint(1)\n```\n"
    result = parse_text(source.encode(), ".md")
    assert result.text == source
    assert {block.kind for block in result.blocks} >= {"heading", "paragraph", "code"}
    for block in result.blocks:
        assert result.text[block.start : block.end] == block.text
        assert block.locations[0]["origin"] == "source"


def test_long_blocks_split_without_missing_characters_and_obey_input_byte_budget():
    source = "汉字" * 800
    artifact = parse_text(source.encode(), ".txt")
    chunks = split_artifact(artifact, size=800, overlap=120, max_bytes=900)
    assert all(len(chunk.text.encode()) <= 900 for chunk in chunks)
    covered = set()
    for chunk in chunks:
        assert chunk.text == source[chunk.start : chunk.end]
        covered.update(range(chunk.start, chunk.end))
    assert covered == set(range(len(source)))


@pytest.mark.parametrize("content", [b"", b" \n\t", b"\xff", b"a\x00b"])
def test_empty_or_binary_text_does_not_create_success_artifact(content):
    with pytest.raises(ApplicationError):
        parse_text(content, ".txt")


def test_cloud_markdown_has_only_normalized_block_locations():
    artifact = parse_text(b"# Title\n\nBody", ".md", source_locations=False)
    assert all(p["origin"] == "normalized" for block in artifact.blocks for p in block.locations)
