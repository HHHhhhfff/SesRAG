"""REAL_001～008：逐格式真实MinerU业务请求；不以旧产物或HTTP200替代。"""

from helpers.case_runner import run_category
from helpers.live_cases import LiveCase

FORMATS = [".docx", ".doc", ".pdf", ".pdf", ".xlsx", ".xls", ".pptx", ".ppt"]


def verify(c):
    # REAL_001 DOCX、002 DOC、003文本PDF、004扫描PDF、005 XLSX、006 XLS、007 PPTX、008 PPT。
    number = int(c.case_id.split("_")[1])
    live = LiveCase(c, {"mineru"})
    try:
        live.upload(FORMATS[number - 1], scanned=number == 4)
    finally:
        live.close()


CASES = {f"REAL_{i:03}": verify for i in range(1, 9)}
if __name__ == "__main__":
    raise SystemExit(run_category(CASES))
