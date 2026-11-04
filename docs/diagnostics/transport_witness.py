"""Bounded metadata witnesses for readonly acquisition diagnostics; no retries."""

from collections.abc import Iterator
from datetime import UTC, datetime

import httpx


class WitnessStream(httpx.SyncByteStream):
    def __init__(self, stream: httpx.SyncByteStream, entry: dict[str, object]) -> None:
        self.stream = stream
        self.entry = entry

    def __iter__(self) -> Iterator[bytes]:
        try:
            yield from self.stream
        except Exception as error:
            self.entry.update(phase="body_failed", error_class=type(error).__name__)
            raise
        else:
            self.entry["phase"] = "body_complete"

    def close(self) -> None:
        self.stream.close()


class TransportWitness(httpx.BaseTransport):
    """Wrap the existing scoped transport without changing policy or admission."""

    def __init__(self, inner: httpx.BaseTransport, maximum: int = 10) -> None:
        if not 1 <= maximum <= 100:
            raise ValueError("invalid_witness_limit")
        self.inner = inner
        self.maximum = maximum
        self.attempts: list[dict[str, object]] = []

    def handle_request(self, request: httpx.Request) -> httpx.Response:
        if len(self.attempts) >= self.maximum:
            raise ValueError("witness_limit_exhausted")
        entry: dict[str, object] = {
            "attempt": len(self.attempts) + 1,
            "started_at": datetime.now(UTC).isoformat(),
            "phase": "started",
        }
        self.attempts.append(entry)
        try:
            response = self.inner.handle_request(request)
        except Exception as error:
            entry.update(phase="request_failed", error_class=type(error).__name__)
            raise
        entry.update(phase="headers_received", status=response.status_code)
        if response.is_stream_consumed:
            entry["phase"] = "body_complete"
            return response
        if not isinstance(response.stream, httpx.SyncByteStream):
            response.close()
            entry["phase"] = "invalid_stream"
            raise TypeError("synchronous_transport_required")
        response.stream = WitnessStream(response.stream, entry)
        return response

    def close(self) -> None:
        self.inner.close()
