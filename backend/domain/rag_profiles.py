"""可冻结的 RAG 配置；元数据版本与运行时凭据分离。"""

from typing import Literal
from urllib.parse import urlsplit

from pydantic import Field, model_validator

from backend.domain.rag import FORMATS, OFFICE_FORMATS, EmbeddingSpace, RetrievalPolicy, StrictModel


class EmbeddingConfig(StrictModel):
    adapter_kind: Literal["mock", "bailian"] = "mock"
    space: EmbeddingSpace
    base_url: str | None = Field(default=None, max_length=500)
    config_ref: Literal["env:RAG_EMBEDDING_API_KEY"] | None = None
    max_input_bytes: int = Field(default=8192, ge=4, le=8192)
    batch_size: int = Field(default=16, ge=1, le=16)
    counter_version: str = "bounded_utf8_v1"
    counter_status: Literal["unverified", "verified"] = "unverified"
    counter_evidence: str | None = Field(default=None, max_length=200)

    @model_validator(mode="after")
    def protocol(self):
        if self.adapter_kind == "mock":
            if self.base_url or self.config_ref or self.space.provider != "mock":
                raise ValueError("Mock配置不能绑定外部服务")
        else:
            url = urlsplit(self.base_url or "")
            if (
                url.scheme != "https"
                or not url.hostname
                or url.username
                or url.password
                or url.query
                or url.fragment
                or self.config_ref is None
                or url.path.rstrip("/") != "/compatible-mode/v1"
                or self.space.provider != "bailian"
                or self.space.model != "qwen3.7-text-embedding"
                or self.space.dimension != 1024
                or self.space.normalization != "l2_float32_v1"
            ):
                raise ValueError("百炼Embedding协议／空间配置无效")
        if self.counter_status == "verified" and not self.counter_evidence:
            raise ValueError("已验证的输入计数必须有可复核依据")
        return self


class RerankConfig(StrictModel):
    adapter_kind: Literal["mock", "bailian"] = "mock"
    model: str = Field(default="qwen3.7-text-rerank", min_length=1, max_length=200)
    revision: str = Field(default="v1", min_length=1, max_length=120)
    endpoint: str | None = Field(default=None, max_length=500)
    config_ref: Literal["env:RAG_RERANK_API_KEY"] | None = None
    max_query_bytes: int = Field(default=2048, ge=4, le=2048)
    max_document_bytes: int = Field(default=4096, ge=4, le=4096)
    max_request_bytes: int = Field(default=65536, ge=8, le=65536)
    counter_version: str = "bounded_utf8_v1"
    counter_status: Literal["unverified", "verified"] = "unverified"
    counter_evidence: str | None = Field(default=None, max_length=200)

    @model_validator(mode="after")
    def protocol(self):
        if self.adapter_kind == "bailian":
            url = urlsplit(self.endpoint or "")
            if (
                url.scheme != "https"
                or not url.hostname
                or url.username
                or url.password
                or url.query
                or url.fragment
                or self.config_ref is None
                or url.path != "/api/v1/services/rerank/text-rerank/text-rerank"
                or self.model != "qwen3.7-text-rerank"
            ):
                raise ValueError("百炼rerank须使用独立原生协议")
        elif self.endpoint or self.config_ref:
            raise ValueError("Mock重排不能含外部地址／凭据")
        if self.counter_status == "verified" and not self.counter_evidence:
            raise ValueError("计数验证缺少依据")
        return self


class ParserConfig(StrictModel):
    parser_kind: Literal["local", "mineru"]
    formats: tuple[str, ...]
    model_version: Literal["vlm", "pipeline"] = "vlm"
    output_protocol: Literal["local_structure_v1", "mineru_cloud_v4_office_text_v1"]
    parse_timeout: int = Field(default=300, ge=1, le=300)
    poll_interval: int = Field(default=5, ge=1, le=30)
    max_polls: int = Field(default=60, ge=1, le=60)
    is_ocr: bool = False
    enable_table: bool = True
    enable_formula: bool = True
    language: str = Field(default="ch", min_length=1, max_length=40)
    verified_formats: tuple[str, ...] = ()
    protocol_evidence: str | None = Field(default=None, max_length=200)

    @model_validator(mode="after")
    def fixed_route(self):
        allowed = {".txt", ".md"} if self.parser_kind == "local" else OFFICE_FORMATS
        if not self.formats or not set(self.formats) <= allowed:
            raise ValueError("Profile格式与固定路由不符")
        if not set(self.verified_formats) <= set(self.formats):
            raise ValueError("验证格式超出声明")
        if self.parser_kind == "local" and self.output_protocol != "local_structure_v1":
            raise ValueError("本地产物协议不匹配")
        if (
            self.parser_kind == "mineru"
            and self.output_protocol != "mineru_cloud_v4_office_text_v1"
        ):
            raise ValueError("云端产物协议不匹配")
        if self.verified_formats and self.parser_kind == "mineru" and not self.protocol_evidence:
            raise ValueError("真实云端格式验证缺少依据")
        return self


class RetrievalConfig(StrictModel):
    policy: RetrievalPolicy = RetrievalPolicy()
    rerank_profile_id: str | None = Field(default=None, max_length=80)
    rerank_profile_version: int | None = Field(default=None, ge=1)

    @model_validator(mode="after")
    def paired(self):
        if (self.rerank_profile_id is None) != (self.rerank_profile_version is None):
            raise ValueError("重排配置须成对")
        if self.policy.rerank_enabled and self.rerank_profile_id is None:
            raise ValueError("启用重排须绑定配置")
        return self


class RetrievalFilters(StrictModel):
    document_ids: tuple[str, ...] | None = Field(default=None, max_length=1000)
    extensions: tuple[str, ...] | None = Field(default=None, max_length=9)
    tags_all: tuple[str, ...] = Field(default=(), max_length=20)

    @model_validator(mode="after")
    def whitelist(self):
        if self.extensions is not None and not set(self.extensions) <= FORMATS:
            raise ValueError("过滤格式不在白名单")
        if any(not v or len(v) > 40 or v != v.strip() for v in self.tags_all):
            raise ValueError("标签无效")
        return self
