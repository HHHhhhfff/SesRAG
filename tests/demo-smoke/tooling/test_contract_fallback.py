"""QLT006：未知校验type/动态loc不得把原输入带进安全错误。"""

import json

import pytest
from fastapi.exceptions import RequestValidationError

from backend.app import create_app
from backend.config import Settings


@pytest.mark.parametrize("location", [("body", "private_dynamic_field", True, 2), ()])
async def test_unknown_validation_error_fallback(location):
    app = create_app(Settings(_env_file=None, redis_enabled=False))
    error = RequestValidationError(
        [
            {
                "type": "private_unknown_type",
                "loc": location,
                "msg": "private_raw_message",
                "input": "private_raw_input",
                "ctx": {"secret": "private_ctx"},
                "url": "https://private.invalid",
            }
        ]
    )
    response = await app.exception_handlers[RequestValidationError](None, error)
    payload = json.loads(response.body)
    assert response.status_code == 422
    assert b"private" not in response.body
    assert payload == {
        "detail": [
            {
                "type": "request_validation",
                "loc": ["body", "field", "field", 2] if location else ["body"],
                "msg": "请求参数校验失败",
            }
        ]
    }
