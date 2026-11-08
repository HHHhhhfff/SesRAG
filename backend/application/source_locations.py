"""公开位置采用规范文本区间，裁剪后只保留实际范围。"""


def clip_locations(locations, start, end, text):
    result = []
    for location in locations:
        left, right = max(start, location["start_offset"]), min(end, location["end_offset"])
        if left >= right:
            continue
        value = {**location, "start_offset": left, "end_offset": right}
        if location["kind"] == "line" and location.get("number"):
            value["number"] = location["number"] + text[location["start_offset"] : left].count("\n")
            value["end_number"] = value["number"] + text[left:right].rstrip("\r\n").count("\n")
        if value not in result:
            result.append(value)
    return result[:1000]


def public_locations(locations, chunk_id, start, end):
    if locations and all("quality" in p and "origin" in p for p in locations):
        return locations
    return (
        [
            {
                "kind": "block",
                "origin": "normalized",
                "quality": "block_only",
                "block_id": chunk_id,
                "start_offset": start,
                "end_offset": end,
            }
        ]
        if end > start
        else []
    )
