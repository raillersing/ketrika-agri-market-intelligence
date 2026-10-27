"""Pace browser qualification without bypassing the application's request quota."""

from collections.abc import Callable
from time import sleep
from typing import Any, Protocol


class BudgetResponse(Protocol):
    @property
    def status(self) -> int: ...

    @property
    def headers(self) -> dict[str, str]: ...


def respect_browser_budget(
    probe: Callable[[], BudgetResponse],
    receipt: dict[str, Any],
    stage: str,
    wait: Callable[[float], None] = sleep,
) -> None:
    """Wait once before exhaustion; never retry an error or alter the limiter."""

    def remaining() -> int:
        response = probe()
        if response.status != 200:
            raise RuntimeError(f"Browser session budget probe failed: HTTP {response.status}")
        limit = int(response.headers["x-ratelimit-limit"])
        value = int(response.headers["x-ratelimit-remaining"])
        if limit != 60 or not 0 <= value < limit:
            raise ValueError("Browser session quota does not match the 60/min contract")
        return value

    value = remaining()
    if value < 20:
        receipt.setdefault("rate_budget_waits", []).append(
            {"stage": stage, "remaining": value, "seconds": 60}
        )
        wait(60)
        if remaining() < 20:
            raise RuntimeError("Browser quota did not recover after one complete window")
