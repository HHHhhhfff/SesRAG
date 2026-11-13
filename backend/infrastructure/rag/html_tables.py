"""只提取MinerU表格中的单元格文本，不执行HTML、脚本或加载任何资产。"""

import re
from html.parser import HTMLParser

from backend.application.errors import PermanentTaskError


class TableText(HTMLParser):
    def __init__(self, protected=()):
        super().__init__(convert_charrefs=True)
        self.protected = protected
        self.rows, self.row, self.cell = [], None, None
        self.header = False
        self.ignored = 0
        self.depth = 0

    def handle_starttag(self, tag, attrs):
        if tag == "table":
            self.depth += 1
            if self.depth > 1:
                raise PermanentTaskError("MINERU_OUTPUT_UNSUPPORTED", "嵌套表格暂不支持")
        if tag in {"script", "style"}:
            self.ignored += 1
        elif not self.ignored:
            if tag == "tr":
                self.row = []
            elif tag in {"td", "th"}:
                self.cell = []
                if not self.rows and tag == "th":
                    self.header = True
            elif tag in {"br", "p", "div"} and self.cell is not None:
                self.cell.append(" ")

    def handle_endtag(self, tag):
        if tag in {"script", "style"}:
            self.ignored = max(0, self.ignored - 1)
        elif not self.ignored:
            if tag in {"td", "th"} and self.cell is not None and self.row is not None:
                value = "".join(self.cell)
                for marker, original in self.protected:
                    value = value.replace(marker, original)
                self.row.append(" ".join(value.split()).replace("|", "\\|"))
                self.cell = None
            elif tag == "tr" and self.row is not None:
                self.rows.append(self.row)
                self.row = None
            elif tag == "table":
                self.depth -= 1

    def handle_data(self, value):
        if self.cell is not None and not self.ignored:
            self.cell.append(value)

    def markdown(self):
        if not self.rows or len(self.rows) > 10000 or max(map(len, self.rows), default=0) > 1000:
            raise PermanentTaskError("MINERU_OUTPUT_UNSUPPORTED", "表格为空或超出上限")
        width = max(map(len, self.rows))
        rows = self.rows if self.header else [[""] * width, *self.rows]
        lines = []
        for number, row in enumerate(rows):
            lines.append("| " + " | ".join([*row, *([""] * (width - len(row)))]) + " |")
            if number == 0:
                lines.append("| " + " | ".join(["---"] * width) + " |")
        return "\n\n" + "\n".join(lines) + "\n\n"


def normalize_html_tables(text, protected=()):
    def convert(match):
        parser = TableText(protected)
        parser.feed(match.group())
        parser.close()
        return parser.markdown()

    return re.sub(r"<table\b[^>]*>.*?</table\s*>", convert, text, flags=re.I | re.S)
