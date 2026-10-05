"""Main entrypoint for FastAPI application."""

from fastapi import FastAPI
from fastapi.responses import JSONResponse

app = FastAPI(
    title="Ketrika Agri Market Intelligence API",
    version="0.1.0",
    docs_url="/v1/docs",
    openapi_url="/v1/openapi.json",
)


@app.get("/v1/health")
async def health_check() -> JSONResponse:
    """Public healthcheck endpoint."""
    return JSONResponse(
        content={
            "status": "ok",
            "version": "0.1.0",
        }
    )
