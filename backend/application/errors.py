class ApplicationError(Exception):
    """可安全返回给 API 客户端的业务错误。"""

    def __init__(
        self, code: str, message: str, status_code: int = 400, *, retryable: bool = False
    ) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.status_code = status_code
        self.retryable = retryable


class TransientTaskError(ApplicationError):
    """允许 Task Runtime 按退避策略重试的错误。"""

    def __init__(self, code: str, message: str) -> None:
        super().__init__(code, message, 503, retryable=True)


class PermanentTaskError(ApplicationError):
    """不应自动重试的 Task 错误。"""

    def __init__(self, code: str, message: str) -> None:
        super().__init__(code, message, 422, retryable=False)
