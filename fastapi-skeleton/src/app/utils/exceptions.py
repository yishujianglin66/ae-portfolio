"""统一异常处理。

业务层抛 `AppError` 的子类（NotFoundError / ConflictError），
由这里的 handler 转成一致结构的 JSON 响应：
  {"error": {"code": "...", "message": "..."}}

好处：上层（API 路由）只需关注成功路径，错误处理集中、可预测。
"""
from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse


class AppError(Exception):
    """业务通用异常，携带 HTTP 状态码与机器可读错误码。"""

    def __init__(self, message: str, *, status_code: int = 400, code: str = "bad_request") -> None:
        self.message = message
        self.status_code = status_code
        self.code = code
        super().__init__(message)


class NotFoundError(AppError):
    def __init__(self, message: str = "Resource not found") -> None:
        super().__init__(message, status_code=404, code="not_found")


class ConflictError(AppError):
    def __init__(self, message: str = "Resource conflict") -> None:
        super().__init__(message, status_code=409, code="conflict")


def _error_body(code: str, message: str) -> dict:
    return {"error": {"code": code, "message": message}}


def register_exception_handlers(app: FastAPI) -> None:
    @app.exception_handler(AppError)
    async def _app_error_handler(_: Request, exc: AppError) -> JSONResponse:
        return JSONResponse(status_code=exc.status_code, content=_error_body(exc.code, exc.message))

    @app.exception_handler(RequestValidationError)
    async def _validation_error_handler(_: Request, exc: RequestValidationError) -> JSONResponse:
        # 把 Pydantic 校验错误也收敛成统一结构，并附带字段级细节便于调试。
        return JSONResponse(
            status_code=422,
            content={
                "error": {
                    "code": "validation_error",
                    "message": "Request validation failed",
                    "detail": exc.errors(),
                }
            },
        )
