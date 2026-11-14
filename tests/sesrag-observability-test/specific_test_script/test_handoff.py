"""A15：端点/字典/来源指纹/Schema与005交接。"""

from evidence import metrics

from backend.infrastructure.observability.metrics import CATALOG


def run():
    # 镜像没有.git，直接核对实际路由/注册；宿主runner另做完整export --check。
    from backend.app import create_app

    actual = {(m.upper(), p) for p, ops in create_app().openapi()["paths"].items() for m in ops}
    declared = {
        (t[0], t[1])
        for i in CATALOG
        if i["logical_id"] == "HTTP_REQUESTS"
        for t in i["allowed_tuples"]
        if t[1].startswith(("/api/", "/health/"))
    }
    assert actual == declared
    counts = {}
    for role in ("api", "worker"):
        output = metrics(role)
        rows = [r for r in output.splitlines() if r and not r.startswith("#")]
        assert len(rows) <= 12000
        assert "_created" not in output
        assert 'service="sesrag-' + role + '"' in output
        assert 'environment="obs-test"' in output
        counts[role] = len(rows)
        for entry in CATALOG:
            if role in entry["roles"] and entry["initialization"] == "required_always":
                assert entry["name"] in output
    return {"series": counts, "honor_labels": True, "metric_families": len(CATALOG)}
