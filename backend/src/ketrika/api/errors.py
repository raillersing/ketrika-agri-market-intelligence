"""RFC 7807 Problem Details error handling for Ketrika API (SPECS §19)."""

from __future__ import annotations

from typing import Any

from fastapi import Request
from fastapi.responses import JSONResponse


class ProblemDetailException(Exception):
    """Base exception complying with RFC 7807 Problem Details."""

    def __init__(
        self,
        status_code: int,
        title: str,
        detail: str,
        type_uri: str = "about:blank",
        instance: str | None = None,
        extra: dict[str, Any] | None = None,
    ) -> None:
        self.status_code = status_code
        self.title = title
        self.detail = detail
        self.type_uri = type_uri
        self.instance = instance
        self.extra = extra or {}
        super().__init__(detail)


class NotFoundException(ProblemDetailException):
    """Resource not found exception (404)."""

    def __init__(self, detail: str = "Resource not found", instance: str | None = None) -> None:
        super().__init__(
            status_code=404,
            title="Not Found",
            detail=detail,
            type_uri="https://api.ketrika.com/errors/not-found",
            instance=instance,
        )


class UnauthorizedException(ProblemDetailException):
    """Authentication required or invalid (401)."""

    def __init__(
        self, detail: str = "Authentication required", instance: str | None = None
    ) -> None:
        super().__init__(
            status_code=401,
            title="Unauthorized",
            detail=detail,
            type_uri="https://api.ketrika.com/errors/unauthorized",
            instance=instance,
        )


class ForbiddenException(ProblemDetailException):
    """Insufficient privileges (403)."""

    def __init__(self, detail: str = "Permission denied", instance: str | None = None) -> None:
        super().__init__(
            status_code=403,
            title="Forbidden",
            detail=detail,
            type_uri="https://api.ketrika.com/errors/forbidden",
            instance=instance,
        )


class BadRequestException(ProblemDetailException):
    """Invalid client request (400)."""

    def __init__(self, detail: str = "Bad request", instance: str | None = None) -> None:
        super().__init__(
            status_code=400,
            title="Bad Request",
            detail=detail,
            type_uri="https://api.ketrika.com/errors/bad-request",
            instance=instance,
        )


def format_problem_response(
    status_code: int,
    title: str,
    detail: str,
    type_uri: str = "about:blank",
    instance: str | None = None,
    extra: dict[str, Any] | None = None,
) -> JSONResponse:
    """Construct RFC 7807 compliant JSONResponse with application/problem+json media type."""
    content: dict[str, Any] = {
        "type": type_uri,
        "title": title,
        "status": status_code,
        "detail": detail,
    }
    if instance:
        content["instance"] = instance
    if extra:
        content.update(extra)

    return JSONResponse(
        status_code=status_code,
        content=content,
        media_type="application/problem+json",
    )


async def problem_exception_handler(request: Request, exc: Any) -> JSONResponse:
    """Handler for ProblemDetailException instances."""
    return format_problem_response(
        status_code=exc.status_code,
        title=exc.title,
        detail=exc.detail,
        type_uri=exc.type_uri,
        instance=exc.instance or str(request.url.path),
        extra=exc.extra,
    )


async def http_exception_handler(request: Request, exc: Any) -> JSONResponse:
    """Handler for standard FastAPI HTTPException converting to RFC 7807."""
    titles = {
        400: "Bad Request",
        401: "Unauthorized",
        403: "Forbidden",
        404: "Not Found",
        409: "Conflict",
        422: "Unprocessable Entity",
        429: "Too Many Requests",
        500: "Internal Server Error",
    }
    title = titles.get(exc.status_code, "Error")
    detail = exc.detail if isinstance(exc.detail, str) else str(exc.detail)
    return format_problem_response(
        status_code=exc.status_code,
        title=title,
        detail=detail,
        type_uri=f"https://api.ketrika.com/errors/{exc.status_code}",
        instance=str(request.url.path),
    )


async def validation_exception_handler(request: Request, exc: Any) -> JSONResponse:
    """Handler for request validation errors (422) conforming to RFC 7807."""
    errors = exc.errors() if hasattr(exc, "errors") else []
    return format_problem_response(
        status_code=422,
        title="Unprocessable Entity",
        detail="Request validation failed",
        type_uri="https://api.ketrika.com/errors/validation-error",
        instance=str(request.url.path),
        extra={"invalid_params": errors},
    )
