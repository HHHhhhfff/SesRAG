"""仅生成本轮合成验收输入；可选下载Apache POI公开旧格式样本，不用于产品解析。"""

import argparse
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent
FACTS = [
    ("Database", "SesRAG stores execution facts in PostgreSQL and vectors in pgvector."),
    ("Notification", "Redis only provides notifications and short lived cache."),
    ("Local text", "TXT and Markdown are parsed locally without MinerU."),
    ("Office", "Office originals are sent to MinerU only after consent for each operation."),
    ("Publishing", "A candidate index becomes active only after all stages succeed."),
    ("Failure", "A failed rebuild preserves the previous active batch."),
    ("Snapshot", "Each new Run freezes its retrieval view and model configuration."),
    ("Retry", "An automatic retry keeps the same Run and user Message."),
    ("Worker", "Every task write requires task id, worker id and generation."),
    ("Citation", "Citations refer only to evidence selected into the actual context."),
    ("Rerank", "Dense similarity and reranker relevance scores are recorded separately."),
    ("Neighbor", "Neighbor expansion stays inside the same document and index batch."),
    ("Unknown", "An unknown remote submission is not automatically submitted again."),
    ("Cancel", "Local cancellation cannot guarantee remote cancellation or refund."),
    ("Limits", "A source file must not exceed ten mebibytes."),
    ("Scope", "One retrieval selects exactly one owned knowledge base."),
    ("Token", "API credentials must never appear in public events or messages."),
    ("Events", "Events use increasing sequence numbers within each Run."),
    ("Empty", "An empty scope is a successful empty search, not a service failure."),
    ("Fallback", "Office parser failures never fall back to a local parser."),
]


def generate(fetch_public=False):
    import xlwt
    from docx import Document
    from openpyxl import Workbook
    from PIL import Image, ImageDraw
    from pptx import Presentation
    from reportlab.lib.utils import ImageReader
    from reportlab.pdfgen.canvas import Canvas

    text = "\n\n".join(f"{title}\n{body}" for title, body in FACTS)
    (ROOT / "knowledge.txt").write_text("本轮合成数据，不含个人信息。\n\n" + text, encoding="utf-8")
    (ROOT / "knowledge.md").write_text(
        "# SesRAG 合成验收资料\n\n"
        + "\n\n".join(f"## {a}\n{b}" for a, b in FACTS)
        + "\n\n| Item | Value |\n| --- | --- |\n| Vector dimension | 1024 |\n",
        encoding="utf-8",
    )
    word = Document()
    word.add_heading("SesRAG synthetic RAG fixture", 0)
    for title, body in FACTS:
        word.add_heading(title, 1)
        word.add_paragraph(body)
    table = word.add_table(rows=1, cols=2)
    table.rows[0].cells[0].text = "Component"
    table.rows[0].cells[1].text = "Responsibility"
    row = table.add_row()
    row.cells[0].text = "PostgreSQL"
    row.cells[1].text = "Durable execution facts"
    word.save(ROOT / "knowledge.docx")
    book = Workbook()
    sheet = book.active
    sheet.title = "RAG Facts"
    sheet.append(["Topic", "Statement"])
    old_book = xlwt.Workbook()
    old_sheet = old_book.add_sheet("RAG Facts")
    for number, row in enumerate([("Topic", "Statement"), *FACTS]):
        if number:
            sheet.append(row)
        for col, value in enumerate(row):
            old_sheet.write(number, col, value)
    book.save(ROOT / "knowledge.xlsx")
    old_book.save(str(ROOT / "knowledge.xls"))
    slides = Presentation()
    for title, body in FACTS[:6]:
        slide = slides.slides.add_slide(slides.slide_layouts[1])
        slide.shapes.title.text = title
        slide.placeholders[1].text = body
    slides.save(ROOT / "knowledge.pptx")
    pdf = Canvas(str(ROOT / "knowledge.pdf"))
    pdf.setTitle("SesRAG synthetic text fixture")
    for offset in range(0, len(FACTS), 10):
        for row, (title, body) in enumerate(FACTS[offset : offset + 10]):
            pdf.setFont("Helvetica-Bold", 12)
            pdf.drawString(40, 800 - row * 70, title)
            pdf.setFont("Helvetica", 9)
            pdf.drawString(40, 780 - row * 70, body)
        pdf.showPage()
    pdf.save()
    image = Image.new("RGB", (1500, 500), "white")
    draw = ImageDraw.Draw(image)
    draw.text(
        (40, 70),
        "Synthetic scan fixture: SesRAG uses PostgreSQL and pgvector.",
        fill="black",
        font_size=36,
    )
    pdf = Canvas(str(ROOT / "knowledge-scan.pdf"))
    pdf.setTitle("SesRAG synthetic scan fixture")
    pdf.drawImage(ImageReader(image), 20, 480, width=560, height=187)
    pdf.save()
    provenance = []
    if fetch_public:
        import httpx

        for kind, name in (("document", "simple.doc"), ("slideshow", "basic_test_ppt_file.ppt")):
            url = f"https://raw.githubusercontent.com/apache/poi/trunk/test-data/{kind}/{name}"
            response = httpx.get(url, timeout=30)
            response.raise_for_status()
            (ROOT / ("public-word.doc" if kind == "document" else "public-slides.ppt")).write_bytes(
                response.content
            )
            provenance.append(
                {
                    "file": "public-word.doc" if kind == "document" else "public-slides.ppt",
                    "source": url,
                    "license": "Apache-2.0",
                }
            )
    files = [
        {
            "file": p.name,
            "bytes": p.stat().st_size,
            "sha256": hashlib.sha256(p.read_bytes()).hexdigest(),
        }
        for p in sorted(ROOT.iterdir())
        if p.suffix in {".txt", ".md", ".doc", ".docx", ".pdf", ".xls", ".xlsx", ".ppt", ".pptx"}
        and p.name != "README.md"
    ]
    (ROOT / "manifest.json").write_text(
        json.dumps(
            {
                "purpose": "PRD-003独立输入；不代表真实解析通过",
                "files": files,
                "third_party": provenance,
            },
            ensure_ascii=False,
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--fetch-public", action="store_true")
    generate(parser.parse_args().fetch_public)
