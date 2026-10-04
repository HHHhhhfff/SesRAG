from backend.infrastructure.rag.chunker import chunk_text


def test_chunk_text_preserves_order_and_offsets():
    chunks = chunk_text("abcdefghij", chunk_size=4, overlap=1)

    assert [chunk.seq for chunk in chunks] == [0, 1, 2]
    assert [chunk.text for chunk in chunks] == ["abcd", "defg", "ghij"]
    assert [(chunk.start_offset, chunk.end_offset) for chunk in chunks] == [
        (0, 4),
        (3, 7),
        (6, 10),
    ]


def test_chunk_text_rejects_invalid_overlap():
    try:
        chunk_text("abc", chunk_size=3, overlap=3)
    except ValueError as exc:
        assert "overlap" in str(exc)
    else:
        raise AssertionError("overlap equal to chunk size must fail")
