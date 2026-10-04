from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True, slots=True)
class ParsedDocument:
    source_name: str
    text: str


def parse_document(path: Path, extension: str) -> ParsedDocument:
    """将首版支持的文本文档转换为统一纯文本。"""
    extension = extension.lower()
    if extension in {".txt", ".md"}:
        return ParsedDocument(source_name=path.name, text=path.read_text(encoding="utf-8"))
    if extension == ".docx":
        from docx import Document

        document = Document(str(path))
        text = "\n".join(paragraph.text for paragraph in document.paragraphs)
        return ParsedDocument(source_name=path.name, text=text)
    raise ValueError(f"unsupported document extension: {extension}")
