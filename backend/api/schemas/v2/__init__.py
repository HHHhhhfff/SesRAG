"""v2 HTTP 投影；不承载事务、身份归属或状态机业务判断。"""

from pydantic import BaseModel, ConfigDict


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid", from_attributes=True)
