"""配置导入和运行选择；数据库是唯一元数据真源，不从文档自动取密钥。"""

import os

from sqlalchemy import select

from backend.application.errors import ApplicationError
from backend.db.rag_models import (
    EmbeddingProfileModel,
    EmbeddingSpaceModel,
    ParserProfileModel,
    RerankProfileModel,
    RetrievalProfileModel,
)
from backend.domain.rag import digest
from backend.domain.rag_profiles import EmbeddingConfig, ParserConfig, RerankConfig, RetrievalConfig

KINDS = {
    "embedding": (EmbeddingProfileModel, EmbeddingConfig),
    "rerank": (RerankProfileModel, RerankConfig),
    "parser": (ParserProfileModel, ParserConfig),
    "retrieval": (RetrievalProfileModel, RetrievalConfig),
}


async def import_profiles(session, entries):
    if not isinstance(entries, list) or len(entries) > 200:
        raise ApplicationError("INVALID_RAG_PARAMETER", "配置文件必须是有界列表", 422)
    for entry in entries:
        if set(entry) - {"kind", "profile_id", "version", "config", "enabled", "blocked"}:
            raise ApplicationError("INVALID_RAG_PARAMETER", "配置项包含未知字段", 422)
        kind, identity, version = entry["kind"], entry["profile_id"], entry["version"]
        if (
            kind not in KINDS
            or not isinstance(identity, str)
            or not 1 <= len(identity) <= 80
            or type(version) is not int
            or version < 1
        ):
            raise ApplicationError("INVALID_RAG_PARAMETER", "配置身份无效", 422)
        model, schema = KINDS[kind]
        config = schema.model_validate(entry["config"]).model_dump(mode="json")
        hashed = digest(config)
        current = await session.get(model, (identity, version))
        if current and current.config_hash != hashed:
            raise ApplicationError(
                "PROFILE_VERSION_CONFLICT", "同版本配置不可修改，请增加版本", 409
            )
        if current is None:
            kwargs = dict(
                profile_id=identity, version=version, config_json=config, config_hash=hashed
            )
            if kind == "embedding":
                space = EmbeddingConfig.model_validate(config).space
                if await session.get(EmbeddingSpaceModel, space.space_id) is None:
                    session.add(
                        EmbeddingSpaceModel(
                            space_id=space.space_id,
                            descriptor_hash=space.space_id,
                            descriptor_json=space.model_dump(),
                            dimension=space.dimension,
                        )
                    )
                    await session.flush()
                kwargs["space_id"] = space.space_id
            current = model(**kwargs)
            session.add(current)
        current.selection_status = "enabled" if entry.get("enabled", True) else "disabled"
        current.security_status = "blocked" if entry.get("blocked", False) else "allowed"
        await session.flush()


async def resolve_profile(session, kind, identity, version, *, frozen=False):
    if kind not in KINDS:
        raise ApplicationError("PROFILE_NOT_FOUND", "配置不存在", 404)
    row = await session.get(KINDS[kind][0], (identity, version))
    if row is None:
        raise ApplicationError("PROFILE_NOT_FOUND", "配置不存在", 404)
    if row.security_status == "blocked" or (not frozen and row.selection_status != "enabled"):
        raise ApplicationError("PROFILE_UNAVAILABLE", "配置已禁用", 409)
    return row


def profile_reason(kind, config, settings=None, extension=None):
    if kind in {"embedding", "rerank"} and config["adapter_kind"] != "mock":
        if config["counter_status"] != "verified":
            return "INPUT_COUNTER_UNVERIFIED"
        alias = config.get("config_ref")
        if not alias or not os.getenv(alias.removeprefix("env:")):
            return "MODEL_CREDENTIAL_UNAVAILABLE"
    if kind == "parser" and config["parser_kind"] == "mineru":
        if settings is None or not settings.mineru_enabled:
            return "MINERU_DISABLED"
        if not settings.mineru_api_key:
            return "MINERU_CREDENTIAL_UNAVAILABLE"
        if not settings.mineru_state_encryption_key or not settings.mineru_storage_host_allowlist:
            return "MINERU_PROFILE_UNAVAILABLE"
        if not config["verified_formats"] or (
            extension and extension not in config["verified_formats"]
        ):
            return "MINERU_PROFILE_UNAVAILABLE"
    return None


def mock_profiles():
    return [
        {
            "kind": "embedding",
            "profile_id": "mock-embedding",
            "version": 1,
            "config": {"space": {"model": "mock-384", "revision": "sha256_v1", "dimension": 384}},
        },
        {"kind": "rerank", "profile_id": "mock-rerank", "version": 1, "config": {}},
        {
            "kind": "parser",
            "profile_id": "local-text",
            "version": 1,
            "config": {
                "parser_kind": "local",
                "formats": [".txt", ".md"],
                "output_protocol": "local_structure_v1",
            },
        },
        {
            "kind": "parser",
            "profile_id": "mineru-office",
            "version": 1,
            "config": {
                "parser_kind": "mineru",
                "formats": [".doc", ".docx", ".pdf", ".xls", ".xlsx", ".ppt", ".pptx"],
                "output_protocol": "mineru_cloud_v4_office_text_v1",
            },
        },
        {
            "kind": "retrieval",
            "profile_id": "default-retrieval",
            "version": 1,
            "config": {"rerank_profile_id": "mock-rerank", "rerank_profile_version": 1},
        },
    ]


async def bootstrap_mock(session):
    # 只供显式初始化／空测试库；不会覆盖已有配置或将旧向量自动确认成Mock。
    exists = await session.scalar(select(EmbeddingProfileModel.profile_id).limit(1))
    if exists is None:
        await import_profiles(session, mock_profiles())


async def select_parser(session, settings, parse, route, extension):
    if parse.parser_profile_id is not None:
        return await resolve_profile(
            session, "parser", parse.parser_profile_id, parse.parser_profile_version
        )
    identity = "local-text" if route == "local" else "mineru-office"
    rows = (
        await session.scalars(
            select(ParserProfileModel)
            .where(
                ParserProfileModel.profile_id == identity,
                ParserProfileModel.selection_status == "enabled",
                ParserProfileModel.security_status == "allowed",
            )
            .order_by(ParserProfileModel.version.desc())
        )
    ).all()
    if not rows:
        raise ApplicationError("PROFILE_UNAVAILABLE", "默认解析配置不可用", 409)
    return next(
        (
            p
            for p in rows
            if extension in p.config_json["formats"]
            and profile_reason("parser", p.config_json, settings, extension) is None
        ),
        rows[0],
    )
