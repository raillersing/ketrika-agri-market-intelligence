"""API helpers can be imported without eagerly constructing the full application."""

from typing import Any

__all__ = ["app"]


def __getattr__(name: str) -> Any:
    if name == "app":
        from ketrika.api.main import app

        return app
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
