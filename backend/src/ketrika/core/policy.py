"""Network and scraping policy engine (SPECS §12).

Enforces:
- robots.txt checks via Protego (cached 24h)
- Token-bucket rate limiting per domain
- Challenge & CAPTCHA detection
- HTTP_OFFLINE enforcement (OfflineError)
- PolicyStop signaling
"""

import re
import threading
import time
from typing import Any
from urllib.parse import urlparse

from protego import Protego

from ketrika.core.settings import get_settings


class PolicyStop(Exception):
    """Raised when crawling or fetching must stop immediately according to security or policy rules."""

    def __init__(self, reason: str, details: dict[str, Any] | None = None) -> None:
        super().__init__(reason)
        self.reason = reason
        self.details = details or {}


class OfflineError(Exception):
    """Raised when a live HTTP request is attempted while HTTP_OFFLINE=1 is enabled."""

    def __init__(self, url: str) -> None:
        super().__init__(f"Network access disabled (HTTP_OFFLINE=1). Cannot fetch: {url}")
        self.url = url


# Regex pattern to detect challenges, captchas and bot protection pages
CHALLENGE_PATTERNS = [
    re.compile(r"captcha", re.IGNORECASE),
    re.compile(r"recaptcha", re.IGNORECASE),
    re.compile(r"hcaptcha", re.IGNORECASE),
    re.compile(r"cf-challenge", re.IGNORECASE),
    re.compile(r"challenge-platform", re.IGNORECASE),
    re.compile(r"just a moment", re.IGNORECASE),
    re.compile(r"attention required", re.IGNORECASE),
]


def detect_challenge(content: str, status_code: int = 200) -> bool:
    """Detect if response content or status indicates an anti-bot challenge or block (SPECS §12)."""
    if status_code in (401, 403):
        return True

    for pattern in CHALLENGE_PATTERNS:
        if pattern.search(content):
            return True
    return False


class TokenBucket:
    """Thread-safe token bucket rate limiter for a single domain."""

    def __init__(self, rate: float, capacity: float = 1.0) -> None:
        self.rate = rate  # tokens added per second
        self.capacity = capacity
        self.tokens = capacity
        self.last_update = time.monotonic()
        self.lock = threading.Lock()

    def acquire(self) -> float:
        """Wait if necessary to acquire a token. Returns elapsed wait time."""
        with self.lock:
            now = time.monotonic()
            elapsed = now - self.last_update
            self.last_update = now

            self.tokens = min(self.capacity, self.tokens + elapsed * self.rate)

            if self.tokens >= 1.0:
                self.tokens -= 1.0
                return 0.0

            needed = 1.0 - self.tokens
            wait_time = needed / self.rate
            time.sleep(wait_time)
            self.last_update = time.monotonic()
            self.tokens = 0.0
            return wait_time


class PolicyEngine:
    """Central policy engine coordinating rate limits, robots.txt and offline rules."""

    def __init__(self) -> None:
        self._rate_limiters: dict[str, TokenBucket] = {}
        self._robots_cache: dict[str, tuple[Protego, float]] = {}  # domain -> (protego, cached_at)
        self._lock = threading.Lock()

    def get_domain_rate(self, domain: str) -> float:
        """Determine max requests per second for domain."""
        settings = get_settings()
        if domain.endswith(".gov.mg") or domain.endswith(".mg"):
            return 0.2
        return settings.http_default_max_rps

    def get_bucket(self, domain: str, max_rps: float | None = None) -> TokenBucket:
        """Get or create token bucket rate limiter for domain."""
        with self._lock:
            if domain not in self._rate_limiters:
                rate = max_rps or self.get_domain_rate(domain)
                self._rate_limiters[domain] = TokenBucket(rate=rate)
            return self._rate_limiters[domain]

    def throttle(self, url: str, max_rps: float | None = None) -> float:
        """Enforce rate limit before fetching URL."""
        parsed = urlparse(url)
        domain = parsed.netloc.lower()
        bucket = self.get_bucket(domain, max_rps)
        return bucket.acquire()

    def set_robots_txt(self, domain: str, robots_content: str) -> None:
        """Cache robots.txt parsed rules for domain."""
        parser = Protego.parse(robots_content)
        with self._lock:
            self._robots_cache[domain] = (parser, time.monotonic())

    def is_allowed_by_robots(self, url: str, user_agent: str | None = None) -> bool:
        """Check if URL is allowed according to cached robots.txt."""
        parsed = urlparse(url)
        domain = parsed.netloc.lower()
        ua = user_agent or get_settings().bot_user_agent

        with self._lock:
            cached = self._robots_cache.get(domain)
            if cached is None:
                return True
            parser, cached_at = cached
            # Expire after 24h (86400s)
            if time.monotonic() - cached_at > 86400:
                del self._robots_cache[domain]
                return True

        return bool(parser.can_fetch(url, ua))

    def check_pre_fetch(self, url: str, max_rps: float | None = None) -> None:
        """Validate offline status and robots.txt permissions before sending request."""
        settings = get_settings()
        if settings.http_offline or int(settings.http_offline) == 1:
            raise OfflineError(url)

        if not self.is_allowed_by_robots(url):
            raise PolicyStop(f"Fetching disallowed by robots.txt: {url}")

        self.throttle(url, max_rps)

    def check_post_fetch(self, content: str, status_code: int = 200, url: str = "") -> None:
        """Validate response content against anti-bot challenges."""
        if detect_challenge(content, status_code):
            raise PolicyStop(
                f"Challenge, CAPTCHA or forbidden status detected on {url} (code={status_code})",
                details={"status_code": status_code, "url": url},
            )


# Global singleton policy engine
_policy_engine: PolicyEngine | None = None


def get_policy_engine() -> PolicyEngine:
    """Return singleton policy engine."""
    global _policy_engine
    if _policy_engine is None:
        _policy_engine = PolicyEngine()
    return _policy_engine
