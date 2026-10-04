from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """集中管理 Demo 配置，环境变量名称与 .env.example 保持一致。"""

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str = "postgresql+psycopg://sesrag:sesrag@postgres:5432/sesrag"
    redis_url: str = "redis://redis:6379/0"
    redis_enabled: bool = True
    auto_create_schema: bool = False
    upload_dir: str = "/data/uploads"
    owner_id: str = "local-user"
    vector_dimension: int = 384
    task_lease_ttl: int = 30
    task_heartbeat_interval: int = 10
    task_max_attempts: int = 3
    task_retry_base_delay: int = 2
    task_deadline: int = 600
    worker_shutdown_grace: int = 20
    queue_poll_interval: float = 1.0
    sse_poll_interval: float = 1.0
    rag_top_k: int = 5
    chunk_size: int = 800
    chunk_overlap: int = 120
    mock_provider: bool = True
    model_base_url: str | None = None
    model_api_key: str | None = None
    model_name: str | None = None
    embedding_model_name: str | None = None

    @property
    def upload_path(self) -> Path:
        return Path(self.upload_dir)


settings = Settings()
