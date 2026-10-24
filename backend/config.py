from pathlib import Path
from typing import Self

from pydantic import Field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """集中管理 Demo 配置，环境变量名称与 .env.example 保持一致。"""

    model_config = SettingsConfigDict(env_file=".env", extra="ignore", hide_input_in_errors=True)

    database_url: str = "postgresql+psycopg://sesrag@postgres:5432/sesrag"
    redis_url: str = "redis://redis:6379/0"
    redis_enabled: bool = True
    auto_create_schema: bool = False
    upload_dir: str = "/data/uploads"
    owner_id: str = "local-user"
    vector_dimension: int = Field(default=384, gt=0)
    task_lease_ttl: int = Field(default=30, gt=0)
    task_heartbeat_interval: int = Field(default=10, gt=0)
    task_max_attempts: int = Field(default=3, gt=0)
    task_retry_base_delay: int = Field(default=2, gt=0)
    task_deadline: int = Field(default=600, gt=0)
    worker_shutdown_grace: int = Field(default=20, gt=0)
    queue_poll_interval: float = Field(default=1.0, gt=0, allow_inf_nan=False)
    sse_poll_interval: float = Field(default=0.2, gt=0, allow_inf_nan=False)
    health_probe_timeout: float = Field(default=2.0, gt=0, allow_inf_nan=False)
    rag_top_k: int = Field(default=5, gt=0)
    chunk_size: int = Field(default=800, gt=0)
    chunk_overlap: int = Field(default=120, ge=0)
    mock_provider: bool = True
    model_base_url: str | None = None
    model_api_key: str | None = None
    model_name: str | None = None
    embedding_model_name: str | None = None

    @model_validator(mode="after")
    def validate_combinations(self) -> Self:
        if not self.mock_provider and not all(
            value and value.strip()
            for value in (
                self.model_base_url,
                self.model_api_key,
                self.model_name,
                self.embedding_model_name,
            )
        ):
            raise ValueError(
                "真实模型需要 MODEL_BASE_URL/MODEL_API_KEY/MODEL_NAME/EMBEDDING_MODEL_NAME"
            )
        if self.vector_dimension != 384:
            raise ValueError("VECTOR_DIMENSION 仅支持 384，与 pgvector 列定义一致")
        # 心跳必须先于租约到期；重叠必须留出实际向前切分的空间。
        if self.task_heartbeat_interval >= self.task_lease_ttl:
            raise ValueError("TASK_HEARTBEAT_INTERVAL 必须小于 TASK_LEASE_TTL")
        if self.chunk_overlap >= self.chunk_size:
            raise ValueError("CHUNK_OVERLAP 必须小于 CHUNK_SIZE")
        return self

    @property
    def upload_path(self) -> Path:
        return Path(self.upload_dir)


settings = Settings()
