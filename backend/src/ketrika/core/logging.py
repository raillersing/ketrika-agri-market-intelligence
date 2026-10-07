"""Structured logging module using structlog."""

import logging
import sys
from typing import Any

import structlog

from ketrika.core.settings import get_settings


def setup_logging() -> None:
    """Configure structlog processors and standard library logging handler."""
    settings = get_settings()

    log_level = getattr(logging, settings.log_level.upper(), logging.INFO)
    logging.basicConfig(
        format="%(message)s",
        stream=sys.stdout,
        level=log_level,
    )

    shared_processors: list[structlog.types.Processor] = [
        structlog.contextvars.merge_contextvars,
        structlog.stdlib.add_logger_name,
        structlog.stdlib.add_log_level,
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.StackInfoRenderer(),
        structlog.processors.format_exc_info,
    ]

    formatter: structlog.types.Processor
    if settings.app_env == "prod" or getattr(settings, "log_format", "console") == "json":
        formatter = structlog.processors.JSONRenderer()
    else:
        formatter = structlog.dev.ConsoleRenderer(colors=True)

    structlog.configure(
        processors=shared_processors
        + [
            structlog.stdlib.ProcessorFormatter.wrap_for_formatter,
        ],
        logger_factory=structlog.stdlib.LoggerFactory(),
        wrapper_class=structlog.stdlib.BoundLogger,
        cache_logger_on_first_use=True,
    )

    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(
        structlog.stdlib.ProcessorFormatter(
            processor=formatter,
            foreign_pre_chain=shared_processors,
        )
    )
    root_logger = logging.getLogger()
    root_logger.handlers = [handler]
    root_logger.setLevel(log_level)


def get_logger(name: str = "ketrika") -> structlog.stdlib.BoundLogger:
    """Return configured structlog bound logger."""
    from typing import cast

    return cast(structlog.stdlib.BoundLogger, structlog.get_logger(name))


def bind_context(**kwargs: Any) -> None:
    """Bind contextual attributes to current logging context."""
    structlog.contextvars.bind_contextvars(**kwargs)


def clear_context() -> None:
    """Clear contextvars bound to current logging context."""
    structlog.contextvars.clear_contextvars()
