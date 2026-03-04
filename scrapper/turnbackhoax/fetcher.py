"""Scrapling-based async fetching with http / dynamic / stealth modes."""
from __future__ import annotations

import asyncio
import logging
import random
from typing import Any, Dict, List, Optional

# Ensure vendored Scrapling is on sys.path
import turnbackhoax  # noqa: F401 — triggers __init__.py path setup

from scrapling import AsyncFetcher, StealthyFetcher

# DynamicFetcher may not be available if playwright is not installed.
try:
    from scrapling import DynamicFetcher
except Exception:  # pragma: no cover
    DynamicFetcher = None  # type: ignore[assignment,misc]

from turnbackhoax.config import FetcherMode, ScrapeConfig

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Response wrapper
# ---------------------------------------------------------------------------
class FetchResult:
    """Thin wrapper so the rest of the package doesn't need to know which
    Scrapling fetcher returned the response."""

    def __init__(self, response: Any, url: str) -> None:
        self._resp = response
        self.url = url

    # --- Expose Scrapling Selector/Response helpers ---

    @property
    def status(self) -> int:
        return getattr(self._resp, "status", 0)

    @property
    def ok(self) -> bool:
        return 200 <= self.status < 400

    @property
    def html(self) -> str:
        """Return the raw HTML string."""
        body = getattr(self._resp, "body", None)
        if isinstance(body, bytes):
            encoding = getattr(self._resp, "encoding", "utf-8") or "utf-8"
            return body.decode(encoding, errors="replace")
        # Scrapling Response stores decoded text in html_content sometimes
        hc = getattr(self._resp, "html_content", None)
        if hc is not None:
            return str(hc)
        return str(body or "")

    # Delegate Scrapling Selector methods directly
    def css(self, query: str) -> Any:
        return self._resp.css(query)

    def xpath(self, query: str) -> Any:
        return self._resp.xpath(query)

    def find(self, *args: Any, **kwargs: Any) -> Any:
        return self._resp.find(*args, **kwargs)

    def find_all(self, *args: Any, **kwargs: Any) -> Any:
        return self._resp.find_all(*args, **kwargs)

    def find_by_text(self, *args: Any, **kwargs: Any) -> Any:
        return self._resp.find_by_text(*args, **kwargs)

    def get_all_text(self, **kwargs: Any) -> str:
        fn = getattr(self._resp, "get_all_text", None)
        if fn:
            return fn(**kwargs)
        # fallback
        text_prop = getattr(self._resp, "text", None)
        return str(text_prop) if text_prop else ""

    @property
    def raw(self) -> Any:
        """Access the underlying Scrapling response object."""
        return self._resp


# ---------------------------------------------------------------------------
# Core fetch functions
# ---------------------------------------------------------------------------
async def fetch_page(
    url: str,
    mode: FetcherMode = "http",
    config: Optional[ScrapeConfig] = None,
) -> FetchResult:
    """Fetch a single URL using the chosen Scrapling fetcher.

    Returns a :class:`FetchResult` wrapping the Scrapling ``Response``.
    Raises on failure after retries are exhausted.
    """
    retries = 3
    timeout = 15

    if mode == "http":
        headers: Dict[str, str] = {}
        if config and config.user_agent:
            headers["User-Agent"] = config.user_agent
        resp = await AsyncFetcher.get(
            url,
            headers=headers or None,
            timeout=timeout,
            retries=retries,
            stealthy_headers=True,
        )
        return FetchResult(resp, url)

    elif mode == "dynamic":
        if DynamicFetcher is None:
            raise RuntimeError(
                "DynamicFetcher requires playwright.  "
                "Install with: pip install playwright && python -m playwright install chromium"
            )
        resp = await DynamicFetcher.async_fetch(
            url,
            headless=True,
            network_idle=True,
            timeout=timeout * 1000,  # ms
            retries=retries,
        )
        return FetchResult(resp, url)

    elif mode == "stealth":
        resp = await StealthyFetcher.async_fetch(
            url,
            headless=True,
            network_idle=True,
            timeout=timeout * 1000,  # ms
            retries=retries,
            google_search=True,
        )
        return FetchResult(resp, url)

    else:
        raise ValueError(f"Unknown fetcher mode: {mode!r}")


async def fetch_many(
    urls: List[str],
    mode: FetcherMode = "http",
    config: Optional[ScrapeConfig] = None,
    concurrency: int = 5,
    min_delay: float = 1.0,
    max_delay: float = 3.0,
) -> List[FetchResult]:
    """Fetch multiple URLs concurrently with a semaphore-based throttle.

    Returns results in the same order as *urls*.  Failed fetches return a
    ``FetchResult`` with ``status == 0`` rather than raising.
    """
    sem = asyncio.Semaphore(concurrency)
    results: List[Optional[FetchResult]] = [None] * len(urls)

    async def _fetch(idx: int, url: str) -> None:
        async with sem:
            try:
                result = await fetch_page(url, mode, config)
                results[idx] = result
            except Exception as exc:
                logger.error("Failed to fetch %s: %s", url, exc)
                # Return a dummy result so callers can check .ok
                results[idx] = FetchResult(_DummyResponse(url, exc), url)
            # Randomised politeness delay
            delay = random.uniform(min_delay, max_delay)
            await asyncio.sleep(delay)

    tasks = [asyncio.create_task(_fetch(i, u)) for i, u in enumerate(urls)]
    await asyncio.gather(*tasks)
    return results  # type: ignore[return-value]


# ---------------------------------------------------------------------------
# Dummy response for failed fetches
# ---------------------------------------------------------------------------
class _DummyResponse:
    """Placeholder returned when a fetch fails, so callers can always check
    ``.ok`` / ``.status`` without try/except."""

    def __init__(self, url: str, error: Exception) -> None:
        self.url = url
        self.error = error
        self.status = 0
        self.body = b""
        self.html_content = ""
        self.text = ""
        self.encoding = "utf-8"

    def css(self, _q: str) -> list:
        return []

    def xpath(self, _q: str) -> list:
        return []

    def find(self, *_a: Any, **_kw: Any) -> None:
        return None

    def find_all(self, *_a: Any, **_kw: Any) -> list:
        return []

    def get_all_text(self, **_kw: Any) -> str:
        return ""
