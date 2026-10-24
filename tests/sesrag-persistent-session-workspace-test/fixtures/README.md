# 合成基线数据

本目录只放不含真实用户内容、Secret 或产品终态的版本化测试素材。

- `baseline.json` 固定 fixture 版本、合成 owner、默认数据库与模型标识，用于运行上下文和报告校验。
- `model-profiles.json` 是通过应用 `sync_model_profiles` 正式导入的非 Secret Profile 元数据；Mock Profile 与 0005 迁移 seed 一致，两个 HTTP Profile 使用虚假 `env:MODEL_API_KEY` 引用和容器内受控 Provider 地址。
- `documents/` 提供后续 RAG 用例的原文哨兵；环境初始化不将它们写入产品数据库、不预造 document/chunk/index。
- Provider 状态仅驻留在单个受控进程内；`tmp/<run_id>/inputs/` 的长文本、恶意 Markdown 和 DOCX 由 `tooling/prepare-fixtures.py` 在需要时生成，结束清理。

任何 fixture 内容变化都应更新 `fixture_version`、对应 hash 和源码指纹；不得将真实 prompt、API Key、数据库口令或跨轮动态 ID 写入这些文件。
