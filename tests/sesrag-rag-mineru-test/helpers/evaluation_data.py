"""只校验评测数据格式与最低覆盖；不执行评测或虚构25题标注。"""

from helpers.common import SUITE, load
from jsonschema import Draft202012Validator


def validate_dataset(value):
    Draft202012Validator(load(SUITE / "fixtures/evaluation.schema.json")).validate(value)
    questions = value["questions"]
    ids = [q["id"] for q in questions]
    if len(ids) != len(set(ids)):
        raise ValueError("DUPLICATE_EVALUATION_QUESTION")
    if (
        sum(q["answerable"] for q in questions) < 20
        or sum(not q["answerable"] for q in questions) < 5
    ):
        raise ValueError("EVALUATION_20_PLUS_5_REQUIRED")
    formats = set()
    for question in questions:
        if question["answerable"] and (
            not question["expected_answer"] or not question["relevant_ranges"]
        ):
            raise ValueError("ANSWER_ANNOTATION_REQUIRED")
        if not question["answerable"] and question["relevant_ranges"]:
            raise ValueError("UNANSWERABLE_CANNOT_HAVE_RELEVANT_RANGES")
        for row in question["relevant_ranges"]:
            if row["end"] <= row["start"]:
                raise ValueError("EVALUATION_RANGE_INVALID")
            formats.add(row["format"])
    if formats != {"txt", "md", "doc", "docx", "pdf", "xls", "xlsx", "ppt", "pptx"}:
        raise ValueError("EVALUATION_NINE_FORMATS_REQUIRED")
    if not any(q["cross_chunk"] for q in questions) or not any(
        q["semantic_distractor"] for q in questions
    ):
        raise ValueError("EVALUATION_SCENARIOS_INCOMPLETE")
    if not {"zh", "en"}.issubset({q["language"] for q in questions}):
        raise ValueError("EVALUATION_LANGUAGES_INCOMPLETE")
    return {"questions": len(questions), "status": "format_ready_not_effect_validated"}
