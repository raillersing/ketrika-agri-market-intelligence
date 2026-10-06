"""Main entrypoint for FastAPI application."""

from fastapi import FastAPI
from fastapi.responses import JSONResponse

from ketrika.core.bronze import check_s3_connection
from ketrika.core.db import check_db_connection

app = FastAPI(
    title="Ketrika Agri Market Intelligence API",
    version="0.1.0",
    docs_url="/v1/docs",
    openapi_url="/v1/openapi.json",
)


@app.get("/v1/health")
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
