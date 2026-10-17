"""Main FastAPI application entrypoint for Ketrika Agri Market Intelligence (SPECS §19)."""

from __future__ import annotations

from collections.abc import AsyncGenerator, Awaitable, Callable
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, Request, Response
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from ketrika.api.auth import ensure_demo_admin
from ketrika.api.errors import (
    ProblemDetailException,
    http_exception_handler,
    problem_exception_handler,
    validation_exception_handler,
)
from ketrika.api.rate_limit import RateLimitMiddleware
from ketrika.api.routers import (
    admin,
    alerts,
    auth,
    bulletins,
    climate,
    copilot,
    coverage,
    economic,
    forecasts,
    kpis,
    locations,
    macro,
    prices,
    products,
    sources,
    stocks,
    supply,
    trade,
    weather,
)
from ketrika.core.bronze import check_s3_connection
from ketrika.core.db import check_db_connection, get_session
from ketrika.core.settings import get_settings


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Application lifespan: seed initial demo admin user if missing."""
    if check_db_connection():
        with get_session() as session:
            ensure_demo_admin(session)
    yield


settings = get_settings()

app = FastAPI(
    title="Ketrika Agri Market Intelligence API",
    description="Official REST API for Madagascar PPN agricultural market intelligence platform.",
    version="0.1.0",
    docs_url="/v1/docs",
    openapi_url="/v1/openapi.json",
    lifespan=lifespan,
)

# CORS configuration
origins = [origin.strip() for origin in settings.cors_origins.split(",") if origin.strip()]
if not origins:
    origins = ["http://localhost:3000", "http://localhost:3005"]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.add_middleware(RateLimitMiddleware)


@app.middleware("http")
async def add_security_headers(
    request: Request,
    call_next: Callable[[Request], Awaitable[Response]],
) -> Response:
    """Inject standard security headers into all responses (SPECS §23)."""
    response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    response.headers["Permissions-Policy"] = "geolocation=(), camera=(), microphone=()"
    if settings.app_env == "prod":
        response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
    return response


# Exception handlers complying with RFC 7807 Problem Details
app.add_exception_handler(ProblemDetailException, problem_exception_handler)
app.add_exception_handler(HTTPException, http_exception_handler)
app.add_exception_handler(RequestValidationError, validation_exception_handler)


# Public Healthcheck
@app.get("/v1/health", tags=["health"])
def health_check() -> JSONResponse:
    """Public healthcheck endpoint reporting DB and S3 connectivity status."""
    db_ok = check_db_connection()
    s3_ok = check_s3_connection()
    all_ok = db_ok and s3_ok
    status = "ok" if all_ok else "degraded"
    status_code = 200 if all_ok else 503

    return JSONResponse(
        status_code=status_code,
        content={
            "status": status,
            "version": "0.1.0",
            "database": "connected" if db_ok else "unreachable",
            "storage": "connected" if s3_ok else "unreachable",
        },
    )


# Include all v1 feature routers
app.include_router(auth.router)
app.include_router(products.router)
app.include_router(locations.router)
app.include_router(prices.router)
app.include_router(coverage.router)
app.include_router(stocks.router)
app.include_router(supply.router)
app.include_router(trade.router)
app.include_router(macro.router)
app.include_router(economic.router)
app.include_router(weather.router)
app.include_router(climate.router)
app.include_router(kpis.router)
app.include_router(forecasts.router)
app.include_router(alerts.router)
app.include_router(bulletins.router)
app.include_router(sources.router)
app.include_router(admin.router)
app.include_router(copilot.router)
