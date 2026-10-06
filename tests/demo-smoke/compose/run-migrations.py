"""将隔离环境连接串注入既有Alembic配置；不替换迁移，也不修改产品入口。"""

import os

from alembic import command
from alembic.config import Config

config = Config("/app/alembic.ini")
# Alembic配置通过ConfigParser插值，URL中的%必须转义；不输出连接凭据。
config.set_main_option("sqlalchemy.url", os.environ["DATABASE_URL"].replace("%", "%%"))
command.upgrade(config, "head")
