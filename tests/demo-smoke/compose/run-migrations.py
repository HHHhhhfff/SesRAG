"""隔离测试运行正式upgrade head；产品env.py已支持DATABASE_URL。"""

import os

from alembic import command
from alembic.config import Config

config = Config("/app/alembic.ini")
# Alembic配置通过ConfigParser插值，URL中的%必须转义；不输出连接凭据。
config.set_main_option("sqlalchemy.url", os.environ["DATABASE_URL"].replace("%", "%%"))
command.upgrade(config, "head")
