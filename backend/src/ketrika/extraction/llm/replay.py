"""Replay LLM client reading pre-recorded responses from disk (SPECS §11.3, AGENTS §5.3 H1)."""

from __future__ import annotations

import json
from pathlib import Path
from typing import TypeVar

from pydantic import BaseModel

from ketrika.extraction.llm.base import (
    LLMPart,
    LLMUsage,
    compute_cache_key,
)

T = TypeVar("T", bound=BaseModel)


class ReplayClient:
    """Mock/Replay LLM client that strictly serves recorded fixtures without network access."""

    provider: str = "replay"
    model: str = "replay-fixture"

    def __init__(self, fixtures_dir: Path | str | None = None) -> None:
        if fixtures_dir is not None:
            self.fixtures_dir = Path(fixtures_dir)
        else:
            from ketrika.core.registry import find_repo_root

            root = find_repo_root()
            self.fixtures_dir = root / "backend" / "tests" / "fixtures" / "llm"

    def extract(
        self,
        schema: type[T],
        parts: list[LLMPart],
        prompt_id: str,
        prompt_version: str = "v1",
        content_sha256: str = "",
        page: int = 1,
    ) -> tuple[T, LLMUsage]:
        """Load fixture by deterministic cache key or fail explicitly."""
        cache_key = compute_cache_key(
            provider=self.provider,
            model=self.model,
            prompt_id=prompt_id,
            prompt_version=prompt_version,
            content_sha256=content_sha256,
            page=page,
        )

        fixture_file = self.fixtures_dir / f"{cache_key}.json"
        if not fixture_file.exists():
            raise KeyError(
                f"Replay fixture missing for cache_key '{cache_key}' (expected at {fixture_file}). "
                "In replay mode, all LLM responses must be recorded in golden sets."
            )

        with open(fixture_file, encoding="utf-8") as f:
            raw_data = json.load(f)

        if "data" in raw_data and "usage" in raw_data:
            data = schema.model_validate(raw_data["data"])
            u = raw_data["usage"]
            usage = LLMUsage(
                input_tokens=u.get("input_tokens", 0),
                output_tokens=u.get("output_tokens", 0),
                cost_usd=float(u.get("cost_usd", 0.0)),
            )
        else:
            data = schema.model_validate(raw_data)
            usage = LLMUsage(input_tokens=100, output_tokens=50, cost_usd=0.0)

        return data, usage
