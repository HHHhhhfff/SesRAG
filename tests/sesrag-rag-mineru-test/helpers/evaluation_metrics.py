"""冻结范围映射及排名指标；只计算给定证据，不将离线结果宣称真实效果。"""


def relevant_chunks(bound_questions, chunks):
    # 映射规则在排名前冻结：同源、同产物hash、半开区间有正重叠即相关。
    identities = [r["chunk_id"] for r in chunks]
    if len(identities) != len(set(identities)):
        raise ValueError("DUPLICATE_CHUNK_ID")
    for chunk in chunks:
        if not 0 <= chunk["start"] < chunk["end"]:
            raise ValueError("CHUNK_RANGE_INVALID")
    result = {}
    for q in bound_questions:
        if not q["answerable"]:
            continue
        hits = set()
        for r in q["relevant_ranges"]:
            overlap = [
                c
                for c in chunks
                if c["source_sha256"] == r["source_sha256"]
                and c["artifact_sha256"] == r["artifact_sha256"]
                and max(c["start"], r["start"]) < min(c["end"], r["end"])
            ]
            if not overlap:
                raise ValueError("ANNOTATED_RANGE_WITHOUT_CHUNK:" + q["id"])
            hits.update(c["chunk_id"] for c in overlap)
        if not hits or q["id"] in result:
            raise ValueError("RELEVANCE_MAPPING_INVALID")
        result[q["id"]] = sorted(hits)
    if not result:
        raise ValueError("RELEVANCE_EMPTY")
    return result


def ranking_metrics(relevant, rankings, *, k):
    if type(k) is not int or k < 1 or not relevant or set(relevant) != set(rankings):
        raise ValueError("EVALUATION_QUESTION_SET_MISMATCH")
    per_question = {}
    for identity, gold in relevant.items():
        ranking = rankings[identity]
        if not gold or len(gold) != len(set(gold)) or len(ranking) != len(set(ranking)):
            raise ValueError("EVALUATION_DUPLICATE_OR_EMPTY_GOLD")
        top = ranking[:k]
        matched = set(top) & set(gold)
        first = next((i for i, hit in enumerate(top, 1) if hit in gold), None)
        per_question[identity] = {
            "recall": len(matched) / len(gold),
            "reciprocal_rank": 1 / first if first else 0,
            "first_relevant_rank": first,
            "relevant_count": len(gold),
            "matched_count": len(matched),
        }
    n = len(per_question)
    return {
        "k": k,
        "questions": n,
        "mean_recall": sum(x["recall"] for x in per_question.values()) / n,
        "mrr": sum(x["reciprocal_rank"] for x in per_question.values()) / n,
        "hit_question_rate": sum(x["matched_count"] > 0 for x in per_question.values()) / n,
        "per_question": per_question,
        "scope": "输入排名的确定性计算；真实性由正式执行证据另验",
    }


def paired_metrics(relevant, dense, reranked, candidates):
    if (
        set(relevant) != set(candidates)
        or set(dense) != set(reranked)
        or set(relevant) != set(dense)
    ):
        raise ValueError("PAIRED_QUESTION_SET_MISMATCH")
    for q in relevant:
        if (
            len(candidates[q]) != len(set(candidates[q]))
            or set(dense[q]) != set(candidates[q])
            or set(reranked[q]) != set(candidates[q])
        ):
            raise ValueError("PAIRED_DENSE_CANDIDATES_MISMATCH")
    before = ranking_metrics(relevant, dense, k=5)
    after = ranking_metrics(relevant, reranked, k=5)
    deltas = {
        q: after["per_question"][q]["reciprocal_rank"]
        - before["per_question"][q]["reciprocal_rank"]
        for q in relevant
    }
    return {
        "dense": before,
        "rerank": after,
        "mrr_delta": after["mrr"] - before["mrr"],
        "improved_questions": [q for q, delta in deltas.items() if delta > 0],
        "declined_questions": [q for q, delta in deltas.items() if delta < 0],
        "recommend_default": after["mrr"] >= before["mrr"] and any(x > 0 for x in deltas.values()),
    }
