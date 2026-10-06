"""Base types and protocol for LLM clients (SPECS §11.3)."""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from typing import Protocol, TypeVar

from pydantic import BaseModel

T = TypeVar("T", bound=BaseModel)


@dataclass(frozen=True)
class LLMPart:
    """A multimodal part sent to LLM (text or page image bytes)."""

    text: str | None = None
    image_bytes: bytes | None = None
    mime_type: str = "image/png"


@dataclass
class LLMUsage:
    """Token usage and estimated cost of an LLM invocation."""

    input_tokens: int = 0
    output_tokens: int = 0
    cost_usd: float = 0.0


@dataclass
class LLMResponse[T]:
    """Structured response from LLM."""

    data: T
    usage: LLMUsage
    cache_key: str
    status: str = "ok"  # ok | cache_hit | refused_budget


def compute_cache_key(
    provider: str,
    model: str,
    prompt_id: str,
    prompt_version: str,
    content_sha256: str,
    page: int = 1,
) -> str:
    """Compute deterministic SHA-256 cache key for LLM responses (SPECS §11.3)."""
    raw = f"{provider}|{model}|{prompt_id}|{prompt_version}|{content_sha256}|{page}"
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


class LLMClient(Protocol):
    """Protocol for LLM extraction clients."""

    provider: str
    model: str

    def extract(
        self,
        schema: type[T],
        parts: list[LLMPart],
        prompt_id: str,
        prompt_version: str = "v1",
        content_sha256: str = "",
        page: int = 1,
    ) -> tuple[T, LLMUsage]:
        """Extract structured data matching target Pydantic schema."""
        ...
