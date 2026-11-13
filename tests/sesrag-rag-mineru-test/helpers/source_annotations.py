"""独立原件投影及金标审计；不调用产品解析器或消费MinerU结果。"""

import hashlib
import re
import struct
import zipfile
from pathlib import Path
from xml.etree import ElementTree as ET

from helpers.common import ROOT, SUITE, load


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def source_projection(path):
    path = Path(path)
    fmt = path.suffix[1:]
    if fmt in {"txt", "md"}:
        return path.read_text(encoding="utf-8-sig")
    if fmt in {"doc", "ppt"}:
        import olefile

        with olefile.OleFileIO(path) as ole:
            raw = ole.openstream("WordDocument" if fmt == "doc" else "PowerPoint Document").read()
        if fmt == "doc":
            # 本固定Word97样本为未压缩英文正文，FIB fcMin/fcMac确定正文而非摘要属性。
            start, end = struct.unpack_from("<II", raw, 24)
            if not (0 < start < end <= len(raw)):
                raise ValueError("SOURCE_DOC_BODY_INVALID")
            return raw[start:end].decode("cp1252")
        texts = []

        def records(data, depth=0):
            if depth > 16:
                raise ValueError("SOURCE_PPT_DEPTH")
            pos = 0
            while pos + 8 <= len(data):
                options, kind, length = struct.unpack_from("<HHI", data, pos)
                end = pos + 8 + length
                if end > len(data):
                    raise ValueError("SOURCE_PPT_RECORD_INVALID")
                payload = data[pos + 8 : end]
                if options & 15 == 15:
                    records(payload, depth + 1)
                elif kind in {4000, 4008}:
                    texts.append(payload.decode("utf-16le" if kind == 4000 else "cp1252"))
                pos = end

        records(raw)
        return "\n".join(texts)
    if fmt == "xls":
        import xlrd

        book = xlrd.open_workbook(path)
        return "\n".join(
            str(cell.value)
            for sheet in book.sheets()
            for row in sheet
            for cell in row
            if cell.value != ""
        )
    if fmt == "pdf":
        from pypdf import PdfReader

        return "\n".join(page.extract_text() or "" for page in PdfReader(path).pages)
    with zipfile.ZipFile(path) as archive:
        if fmt == "docx":
            members = ["word/document.xml"]
            tag = "}t"
        elif fmt == "pptx":
            members = sorted(
                (x for x in archive.namelist() if re.fullmatch(r"ppt/slides/slide\d+\.xml", x)),
                key=lambda x: int(re.search(r"(\d+)\.xml", x)[1]),
            )
            tag = "}t"
        elif fmt == "xlsx":
            # 此固定生成器使用inlineStr；按sheet XML文档顺序投影每个文本节点。
            members = sorted(
                x
                for x in archive.namelist()
                if x.startswith("xl/worksheets/sheet") and x.endswith(".xml")
            )
            tag = "}t"
        else:
            raise ValueError("SOURCE_FORMAT_UNSUPPORTED")
        return "\n".join(
            node.text or ""
            for name in members
            for node in ET.fromstring(archive.read(name)).iter()
            if node.tag.endswith(tag)
        )


def audit_annotations(value, source_root=None):
    from jsonschema import Draft202012Validator

    Draft202012Validator(load(SUITE / "fixtures/source-annotations.schema.json")).validate(value)
    source_root = Path(
        source_root
        or (
            ROOT / "tests/fixtures/rag-v3"
            if (ROOT / "tests/fixtures/rag-v3").is_dir()
            else "/inputs"
        )
    )
    sources = {}
    for source in value["sources"]:
        path = source_root / source["file"]
        if (
            path.parent.resolve() != source_root.resolve()
            or sha(path.read_bytes()) != source["source_sha256"]
        ):
            raise ValueError("ANNOTATION_SOURCE_HASH")
        if source["format"] != path.suffix[1:] or source["source_sha256"] in sources:
            raise ValueError("ANNOTATION_SOURCE_IDENTITY")
        text = source_projection(path)
        if sha(text.encode()) != source["projection_sha256"]:
            raise ValueError("ANNOTATION_PROJECTION_HASH")
        sources[source["source_sha256"]] = (source, text)
    qs = value["questions"]
    if len({q["id"] for q in qs}) != len(qs):
        raise ValueError("ANNOTATION_DUPLICATE_ID")
    if sum(q["answerable"] for q in qs) < 20 or sum(not q["answerable"] for q in qs) < 5:
        raise ValueError("ANNOTATION_20_PLUS_5")
    covered = set()
    for q in qs:
        if q["answerable"] != bool(q["ranges"]) or q["answerable"] != bool(q["expected_answer"]):
            raise ValueError("ANNOTATION_ANSWER_SHAPE")
        if not q["answerable"] and not q["absence_basis"]:
            raise ValueError("ANNOTATION_ABSENCE_BASIS")
        for r in q["ranges"]:
            if r["source_sha256"] not in sources:
                raise ValueError("ANNOTATION_SOURCE_UNKNOWN")
            source, text = sources[r["source_sha256"]]
            if (
                not (0 <= r["start"] < r["end"] <= len(text))
                or text[r["start"] : r["end"]] != r["quote"]
            ):
                raise ValueError("ANNOTATION_SOURCE_RANGE")
            covered.add(source["format"])
    if covered != set("txt md doc docx pdf xls xlsx ppt pptx".split()):
        raise ValueError("ANNOTATION_NINE_FORMATS")
    if (
        not {"zh", "en"} <= {q["language"] for q in qs}
        or not any(q["cross_chunk"] and len(q["ranges"]) > 1 for q in qs)
        or not any(q["semantic_distractor"] for q in qs)
    ):
        raise ValueError("ANNOTATION_SCENARIOS")
    return {
        "questions": len(qs),
        "answerable": sum(q["answerable"] for q in qs),
        "formats": sorted(covered),
        "status": "source_annotations_audited_not_effect_evaluated",
    }


def bind_source(value, source_sha256, artifact_text, artifact_sha256):
    # 只接受真实只读产物；独立quote缺失或重复均失败，不制造区间。
    if sha(artifact_text.encode()) != artifact_sha256:
        raise ValueError("ARTIFACT_HASH_MISMATCH")
    rows = []
    formats = {s["source_sha256"]: s["format"] for s in value["sources"]}
    for q in value["questions"]:
        ranges = []
        for r in q["ranges"]:
            if r["source_sha256"] != source_sha256:
                continue
            quote = r["quote"]
            start = artifact_text.find(quote)
            if start < 0 or artifact_text.find(quote, start + 1) >= 0:
                raise ValueError("ARTIFACT_QUOTE_MISSING_OR_AMBIGUOUS:" + q["id"])
            ranges.append(
                {
                    "source_sha256": source_sha256,
                    "artifact_sha256": artifact_sha256,
                    "start": start,
                    "end": start + len(quote),
                    "format": formats[source_sha256],
                }
            )
        if ranges:
            rows.append({"id": q["id"], "relevant_ranges": ranges})
    return {"source_sha256": source_sha256, "artifact_sha256": artifact_sha256, "questions": rows}
