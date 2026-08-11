"""Custom application exceptions and FastAPI handlers.

All business errors raised inside the API should use :class:`AppException` with a
code from :class:`app.core.errors.ErrorCode`. The (status, message) tuple is
resolved automatically; callers may override the message via ``detail`` and add
context via ``extras``.

Backward-compat shims (:class:`NotFoundError`, :class:`PermissionDeniedError`,
:class:`ConflictError`, :class:`ValidationError`, :class:`AuthenticationError`)
are still exported so legacy code keeps working until it is migrated. Internally
they all map to the new code-based handler.
"""

from __future__ import annotations

from typing import Any

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.core.errors import ERROR_MESSAGES, ErrorCode
from app.core.logger import get_logger


logger = get_logger("exceptions")


class AppException(Exception):
    """Business exception carrying an :class:`ErrorCode`.

    Attributes:
        code: One of :class:`ErrorCode`.
        status_code: HTTP status returned to the client.
        message: French message displayed to the user (taken from
            :data:`ERROR_MESSAGES` unless overridden via ``detail``).
        extras: Arbitrary JSON-serialisable context (e.g. invalid field list).
    """

    def __init__(
        self,
        code: ErrorCode | str,
        detail: str | None = None,
        extras: dict[str, Any] | None = None,
        *,
        status_code: int | None = None,
    ) -> None:
        # Allow passing either an enum member or a raw string code (for legacy).
        if isinstance(code, ErrorCode):
            self.code = code
            default_status, default_msg = ERROR_MESSAGES[code]
        else:
            try:
                resolved = ErrorCode(code)
                self.code = resolved
                default_status, default_msg = ERROR_MESSAGES[resolved]
            except ValueError:
                # Unknown code -> fall back to BAD_REQUEST while preserving the string.
                self.code = ErrorCode.BAD_REQUEST  # type: ignore[assignment]
                default_status, default_msg = ERROR_MESSAGES[ErrorCode.BAD_REQUEST]
        self.status_code = status_code if status_code is not None else default_status
        self.message = detail or default_msg
        self.extras = extras or {}
        super().__init__(self.message)

    @property
    def code_value(self) -> str:
        """String value of the code (e.g. ``"AUTH_1001"``)."""
        return self.code.value if isinstance(self.code, ErrorCode) else str(self.code)


# ---------------------------------------------------------------------------
# Backward-compatible subclasses (so existing CRUD modules keep working).
# Once everything is migrated to ``AppException(ErrorCode.XXX)`` these can be
# deleted.
# ---------------------------------------------------------------------------


class NotFoundError(AppException):
    def __init__(self, message: str | None = None, *, code: ErrorCode = ErrorCode.NOT_FOUND) -> None:
        super().__init__(code, detail=message)


class PermissionDeniedError(AppException):
    def __init__(self, message: str | None = None, *, code: ErrorCode = ErrorCode.FORBIDDEN) -> None:
        super().__init__(code, detail=message)


class ConflictError(AppException):
    def __init__(self, message: str | None = None, *, code: ErrorCode = ErrorCode.CONFLICT) -> None:
        super().__init__(code, detail=message)


class ValidationError(AppException):
    def __init__(
        self, message: str | None = None, *, code: ErrorCode = ErrorCode.VALIDATION_ERROR
    ) -> None:
        super().__init__(code, detail=message)


class AuthenticationError(AppException):
    def __init__(
        self, message: str | None = None, *, code: ErrorCode = ErrorCode.INVALID_CREDENTIALS
    ) -> None:
        super().__init__(code, detail=message)


# ---------------------------------------------------------------------------
# Handlers
# ---------------------------------------------------------------------------


def _http_status_to_code(status: int) -> ErrorCode:
    """Best-effort mapping for native ``HTTPException``."""
    if status == 400:
        return ErrorCode.BAD_REQUEST
    if status == 401:
        return ErrorCode.TOKEN_INVALID
    if status == 403:
        return ErrorCode.FORBIDDEN
    if status == 404:
        return ErrorCode.NOT_FOUND
    if status == 409:
        return ErrorCode.CONFLICT
    if status == 410:
        return ErrorCode.FILE_PHYSICALLY_MISSING
    if status in (413,):
        return ErrorCode.FILE_TOO_LARGE
    if status == 415:
        return ErrorCode.INVALID_FILE_TYPE
    if status == 422:
        return ErrorCode.VALIDATION_ERROR
    if status == 429:
        return ErrorCode.RATE_LIMIT_EXCEEDED
    if status == 503:
        return ErrorCode.SERVICE_UNAVAILABLE
    if status >= 500:
        return ErrorCode.INTERNAL_ERROR
    return ErrorCode.BAD_REQUEST


def register_exception_handlers(app: FastAPI) -> None:
    """Wire exception handlers on the FastAPI app."""

    @app.exception_handler(AppException)
    async def _handle_app_exception(_: Request, exc: AppException) -> JSONResponse:
        logger.warning("AppException: %s (code=%s)", exc.message, exc.code_value)
        return JSONResponse(
            status_code=exc.status_code,
            content={
                "code": exc.code_value,
                "message": exc.message,
                "extras": exc.extras,
                # Legacy keys kept for any old client still reading them.
                "error": exc.code_value,
                "details": exc.extras,
            },
        )

    @app.exception_handler(StarletteHTTPException)
    async def _handle_http_exception(_: Request, exc: StarletteHTTPException) -> JSONResponse:
        code = _http_status_to_code(exc.status_code)
        default_message = ERROR_MESSAGES[code][1]
        if isinstance(exc.detail, str) and exc.detail:
            message = exc.detail
        else:
            message = default_message
        return JSONResponse(
            status_code=exc.status_code,
            content={
                "code": code.value,
                "message": message,
                "extras": exc.detail if not isinstance(exc.detail, str) else {},
                # Legacy keys
                "error": code.value,
                "details": exc.detail if not isinstance(exc.detail, str) else {},
            },
        )

    @app.exception_handler(RequestValidationError)
    async def _handle_validation_error(_: Request, exc: RequestValidationError) -> JSONResponse:
        # Build a compact list of "<loc>: <msg>" for the user.
        errors = exc.errors()
        fields: list[str] = []
        for err in errors:
            loc = ".".join(str(p) for p in err.get("loc", ()) if p not in ("body", "query", "path"))
            if loc:
                fields.append(loc)
        extras: dict[str, Any] = {"errors": errors}
        if fields:
            extras["fields"] = fields
        return JSONResponse(
            status_code=422,
            content={
                "code": ErrorCode.VALIDATION_ERROR.value,
                "message": ERROR_MESSAGES[ErrorCode.VALIDATION_ERROR][1],
                "extras": extras,
                # Legacy
                "error": ErrorCode.VALIDATION_ERROR.value,
                "details": errors,
            },
        )

    @app.exception_handler(Exception)
    async def _handle_unexpected(_: Request, exc: Exception) -> JSONResponse:
        logger.exception("Unhandled exception: %s", exc)
        return JSONResponse(
            status_code=500,
            content={
                "code": ErrorCode.INTERNAL_ERROR.value,
                "message": ERROR_MESSAGES[ErrorCode.INTERNAL_ERROR][1],
                "extras": {},
                # Legacy
                "error": ErrorCode.INTERNAL_ERROR.value,
                "details": {},
            },
        )


__all__ = [
    "AppException",
    "AuthenticationError",
    "ConflictError",
    "NotFoundError",
    "PermissionDeniedError",
    "ValidationError",
    "register_exception_handlers",
]
