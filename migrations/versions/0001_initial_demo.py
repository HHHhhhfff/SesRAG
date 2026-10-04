"""创建 SesRAG Demo 首版业务表和 pgvector 扩展。"""

from alembic import op

from backend.db.base import Base
from backend.db import models  # noqa: F401 - 确保 metadata 已注册

revision = "0001_initial_demo"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")
    bind = op.get_bind()
    Base.metadata.create_all(bind=bind)


def downgrade() -> None:
    bind = op.get_bind()
    Base.metadata.drop_all(bind=bind)

