-- PRD-004固定身份由OWNER_ID=obs-test提供；其余业务对象由各组独立API创建。
-- 使用当前0012迁移，不写入跨轮伪造业务状态。
SELECT CASE WHEN version_num = '0012_task_trace_origin' THEN 1 ELSE 0 END AS schema_ready
FROM alembic_version;
