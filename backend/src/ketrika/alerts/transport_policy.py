"""Local capture is not authorisation for external delivery (AGENTS H3, ADR-122)."""

from ketrika.core.settings import Settings


def permits_local_smtp_capture(settings: Settings, host: str, port: int) -> bool:
    """Only the explicitly named, non-relaying Compose Mailpit service is permitted."""
    return settings.app_env in {"dev", "test"} and host == "mailpit" and port == 1025
