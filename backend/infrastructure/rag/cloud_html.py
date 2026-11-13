"""云端正文入库前清理 HTML；Markdown 代码区保持字面语义。"""

import re
from html.parser import HTMLParser

from markdown_it import MarkdownIt
from markdown_it.rules_inline.backticks import backtick

from backend.infrastructure.rag.html_tables import normalize_html_tables


class SafeCloudHTML(HTMLParser):
    dangerous = {"script", "style", "iframe", "object", "svg", "math", "template", "noscript"}
    tables = {"table", "thead", "tbody", "tfoot", "tr", "td", "th", "caption"}

    def __init__(self):
        super().__init__(convert_charrefs=False)
        self.output = []
        self.blocked = []

    def handle_starttag(self, tag, attrs):
        if tag in self.dangerous:
            self.blocked.append(tag)
        elif not self.blocked and tag in self.tables:
            self.output.append(f"<{tag}>")
        elif not self.blocked and tag in {"br", "p", "div"}:
            self.output.append("\n")

    def handle_startendtag(self, tag, attrs):
        if tag not in self.dangerous:
            self.handle_starttag(tag, attrs)

    def handle_endtag(self, tag):
        if self.blocked:
            if tag == self.blocked[-1]:
                self.blocked.pop()
        elif tag in self.tables:
            self.output.append(f"</{tag}>")
        elif tag in {"p", "div"}:
            self.output.append("\n")

    def handle_data(self, data):
        if not self.blocked:
            self.output.append(data)

    def handle_entityref(self, name):
        self.handle_data(f"&{name};")

    def handle_charref(self, name):
        self.handle_data(f"&#{name};")


def normalize_cloud_html(text):
    lines = text.splitlines(keepends=True)
    offsets = [0]
    for line in lines:
        offsets.append(offsets[-1] + len(line))
    ranges = []
    parser = MarkdownIt("commonmark", {"html": True})

    def source_backticks(state, silent):
        start, count = state.pos, len(state.tokens)
        matched = backtick(state, silent)
        if not silent and len(state.tokens) > count and state.tokens[-1].type == "code_inline":
            state.tokens[-1].meta["source_span"] = (start, state.pos)
        return matched

    # 复用真正的行内规则，转义反引号和 html_block 内字面反引号不构成代码。
    parser.inline.ruler.at("backticks", source_backticks)
    for token in parser.parse(text):
        if token.type in {"fence", "code_block"} and token.map:
            ranges.append((offsets[token.map[0]], offsets[token.map[1]]))
        elif token.type == "inline" and token.map:
            # inline.content 去掉了列表/引用前缀；逐行回映到原文，保留原始代码字面值。
            cursor, limit = offsets[token.map[0]], offsets[token.map[1]]
            positions = []
            for line in token.content.splitlines(keepends=True):
                fragment = line.rstrip("\n")
                found = text.find(fragment, cursor, limit)
                if found < 0:
                    positions = []
                    break
                positions.extend(range(found, found + len(fragment)))
                cursor = found + len(fragment)
                if line.endswith("\n"):
                    newline = text.find("\n", cursor, limit)
                    if newline < 0:
                        positions = []
                        break
                    positions.append(newline)
                    cursor = newline + 1
            for child in token.children or ():
                span = child.meta.get("source_span") if child.type == "code_inline" else None
                if span and len(positions) == len(token.content):
                    start, end = span
                    ranges.append((positions[start], positions[end - 1] + 1))
    ranges.sort()
    protected = []
    prefix = "SES_RAG_CODE_"
    while prefix in text:
        prefix += "X"
    for start, end in reversed(ranges):
        marker = f"{prefix}{len(protected)}_END"
        protected.append((marker, text[start:end]))
        text = text[:start] + marker + text[end:]
    text = re.sub(r"!\[[^\]\n]*\]\([^\n]*?\)|!\[[^\]\n]*\]\[[^\]\n]*\]", "", text)
    parser = SafeCloudHTML()
    parser.feed(text)
    parser.close()
    cleaned = normalize_html_tables("".join(parser.output), protected)
    for marker, original in protected:
        cleaned = cleaned.replace(marker, original)
    return cleaned
