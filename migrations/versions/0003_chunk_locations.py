"""保存解析器基础位置；旧索引不伪造历史位置信息。"""

import sqlalchemy as sa
from alembic import op

revision = "0003_chunk_locations"
down_revision = "0002_demo_integrity"
branch_labels = None
depends_on = None


def upgrade():
    if "locations_json" not in {c["name"] for c in sa.inspect(op.get_bind()).get_columns("chunks")}:
        op.add_column(
            "chunks", sa.Column("locations_json", sa.JSON(), nullable=False, server_default="[]")
        )


def downgrade():
    # 旧应用可忽略此列；回退版本不删除已经发布的证据位置。
    pass
