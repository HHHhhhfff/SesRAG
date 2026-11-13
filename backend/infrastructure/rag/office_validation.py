"""原件格式安全预检；不提取办公正文、不运行 Office 或转换格式。"""

import io
import unicodedata
from pathlib import Path
from zipfile import BadZipFile, ZipFile

import olefile
from defusedxml import ElementTree

from backend.application.errors import ApplicationError
from backend.domain.rag import FORMATS, TEXT_FORMATS

MIMES = {
    ".txt": {"text/plain"},
    ".md": {"text/plain", "text/markdown"},
    ".pdf": {"application/pdf"},
    ".doc": {"application/msword"},
    ".xls": {"application/vnd.ms-excel"},
    ".ppt": {"application/vnd.ms-powerpoint"},
    ".docx": {"application/vnd.openxmlformats-officedocument.wordprocessingml.document"},
    ".xlsx": {"application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"},
    ".pptx": {"application/vnd.openxmlformats-officedocument.presentationml.presentation"},
}


def validate_source(filename, mime, content):
    name = filename.replace("\\", "/").rsplit("/", 1)[-1]
    if (
        not name
        or len(name) > 255
        or ":" in name
        or any(ord(c) < 32 or ord(c) == 127 for c in name)
    ):
        raise ApplicationError("INVALID_DOCUMENT_FILENAME", "文件名无效", 422)
    extension = Path(name).suffix.lower()
    if extension not in FORMATS:
        raise ApplicationError("UNSUPPORTED_DOCUMENT_TYPE", "文件格式不受支持", 415)
    if len(content) > 10 * 1024 * 1024:
        raise ApplicationError("DOCUMENT_TOO_LARGE", "文档大小不能超过10MiB", 413)
    if not content:
        raise ApplicationError("EMPTY_DOCUMENT", "文件为空", 422)
    if mime not in MIMES[extension] | {None, "application/octet-stream"}:
        raise ApplicationError("DOCUMENT_MIME_MISMATCH", "扩展名和MIME不匹配", 415)
    try:
        if extension in TEXT_FORMATS:
            text = content.decode("utf-8-sig")
            if not text.strip() or "\x00" in text:
                raise ValueError()
        elif extension == ".pdf":
            if not content.startswith(b"%PDF-") or b"%%EOF" not in content[-4096:]:
                raise ValueError()
        elif extension in {".docx", ".xlsx", ".pptx"}:
            expected = {
                ".docx": "word/document.xml",
                ".xlsx": "xl/workbook.xml",
                ".pptx": "ppt/presentation.xml",
            }[extension]
            with ZipFile(io.BytesIO(content)) as archive:
                infos = archive.infolist()
                if len(infos) > 10000 or sum(i.file_size for i in infos) > 40 * 1024**2:
                    raise ValueError()
                names = set()
                for info in infos:
                    path = info.filename.replace("\\", "/")
                    lower = unicodedata.normalize("NFC", path).casefold()
                    if (
                        path.startswith("/")
                        or ".." in path.split("/")
                        or ":" in path
                        or lower in names
                        or len(path) > 240
                        or "vbaproject" in lower
                        or "/embeddings/" in lower
                        or info.flag_bits & 1
                        or (info.external_attr >> 16) & 0o170000 == 0o120000
                    ):
                        raise ValueError()
                    names.add(lower)
                if (
                    expected not in archive.namelist()
                    or "[Content_Types].xml" not in archive.namelist()
                ):
                    raise ValueError()
                types = archive.read("[Content_Types].xml")
                if b"macroEnabled" in types:
                    raise ValueError()
                ElementTree.fromstring(types)
                for info in infos:
                    if info.filename.endswith(".rels"):
                        tree = ElementTree.fromstring(archive.read(info))
                        if any(
                            node.get("TargetMode") == "External"
                            and not node.get("Type", "").endswith("/hyperlink")
                            for node in tree
                        ):
                            raise ValueError()
        else:
            if not olefile.isOleFile(io.BytesIO(content)):
                raise ValueError()
            with olefile.OleFileIO(
                io.BytesIO(content), raise_defects=olefile.DEFECT_INCORRECT
            ) as ole:
                streams = ole.listdir()
                if len(streams) > 10000:
                    raise ValueError()
                names = {parts[-1].casefold() for parts in streams}
                expected = {
                    ".doc": {"worddocument"},
                    ".xls": {"workbook", "book"},
                    ".ppt": {"powerpoint document"},
                }[extension]
                if not names & expected or any(
                    any(
                        token in "/".join(parts).casefold()
                        for token in ("vba", "encryptedpackage", "encryptioninfo", "objectpool")
                    )
                    for parts in streams
                ):
                    raise ValueError()
    except (ValueError, UnicodeError, BadZipFile, OSError, KeyError):
        raise ApplicationError("SOURCE_UNSAFE", "文件内容无效、不匹配或超过安全边界", 422) from None
    return name, extension
