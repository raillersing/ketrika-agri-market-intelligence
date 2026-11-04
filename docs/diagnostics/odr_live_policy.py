"""Do not turn quota exhaustion or local offline mode into a source ban."""


def source_must_stop(reason: str) -> bool:
    return reason.startswith("Fetching disallowed by robots.txt:") or reason in {
        "http_access_refused",
        "Challenge, CAPTCHA or forbidden status detected",
    }
