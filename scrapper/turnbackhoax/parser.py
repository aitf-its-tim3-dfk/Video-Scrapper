"""HTML parsing — article link extraction and video URL detection.

Uses Scrapling CSS selectors instead of BeautifulSoup.
"""
from __future__ import annotations

import logging
import re
from typing import Any, Dict, List, Optional, Set
from urllib.parse import urljoin, urlparse

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Article links from a listing page
# ---------------------------------------------------------------------------
def find_article_links_from_listing(response: Any, base_url: str) -> List[Dict[str, Optional[str]]]:
    """Extract article links from a TurnBackHoax listing page.

    *response* is a :class:`~turnbackhoax.fetcher.FetchResult` (has ``.css()``
    and ``.find_all()``).

    Returns a list of dicts ``{"url": str, "category": str | None}``.
    """
    links: List[Dict[str, Optional[str]]] = []

    # Cards have class 'news-card-h-alt'
    cards = response.css(".news-card-h-alt")

    for card in cards:
        # Prefer link inside the article-origin / custom-styling-editor block
        target = None
        wrapper = card.css(".article-origin.custom-styling-editor")
        if wrapper:
            target = wrapper[0]
        else:
            target = card

        # Find first anchor with href
        anchors = target.css("a[href]")
        if not anchors:
            continue

        href = _get_attr(anchors[0], "href")
        if not href or href.startswith("#"):
            continue

        full_url = urljoin(base_url, href.strip())

        # Try to find category text
        category: Optional[str] = None
        all_anchors = card.css("a[href]")
        for a in all_anchors:
            a_href = _get_attr(a, "href")
            if a_href and "category=" in a_href:
                a_text = _get_text(a)
                if a_text:
                    category = a_text.strip()
                break

        links.append({"url": full_url, "category": category})

    return links


# ---------------------------------------------------------------------------
# Video URL detection from an article page
# ---------------------------------------------------------------------------
def detect_video_urls(response: Any, debug: bool = False) -> Set[str]:
    """Scan an article page for embedded video URLs.

    *response* is a :class:`~turnbackhoax.fetcher.FetchResult`.

    Returns a set of probable video URLs found in iframes, anchors, and
    visible text within the article wrapper.
    """
    found: Set[str] = set()

    # Prefer the article wrapper
    wrapper_els = response.css(".article-origin.custom-styling-editor")
    root = wrapper_els[0] if wrapper_els else response

    # --- Check iframes ---
    for iframe in root.css("iframe[src]"):
        src = _get_attr(iframe, "src")
        if not src:
            continue
        if "mafindoid" in src.lower():
            if debug:
                logger.debug("    Skipping MafindoID iframe: %s", src)
            continue
        if _is_probable_video_url(src, debug):
            found.add(src)

    # --- Check anchors ---
    for a in root.css("a[href]"):
        href = _get_attr(a, "href")
        if not href:
            continue
        href = href.strip()
        a_text = _get_text(a)
        if "mafindoid" in href.lower() or (a_text and "mafindoid" in a_text.lower()):
            if debug:
                logger.debug("    Skipping MafindoID link: %s", href)
            continue
        if _is_probable_video_url(href, debug):
            found.add(href)

    # --- Check visible text for bare URLs ---
    text = root.get_all_text(separator=" ") if hasattr(root, "get_all_text") else _get_text(root)
    if text:
        for token in text.split():
            if not token.startswith("http"):
                continue
            if "mafindoid" in token.lower():
                continue
            if _is_probable_video_url(token, debug):
                found.add(token)

    return found


# ---------------------------------------------------------------------------
# Article text / title extraction for keyword matching
# ---------------------------------------------------------------------------
def extract_article_text_and_title(response: Any) -> tuple[str, Optional[str]]:
    """Return ``(body_text, title)`` from the article page."""
    wrapper_els = response.css(".article-origin.custom-styling-editor")
    root = wrapper_els[0] if wrapper_els else response

    # Body text
    body_text = ""
    if hasattr(root, "get_all_text"):
        body_text = root.get_all_text(separator=" ", strip=True) or ""
    else:
        body_text = _get_text(root)

    # Title — try h1 inside wrapper, then any h1, then og:title meta
    title: Optional[str] = None
    h1_els = root.css("h1")
    if not h1_els:
        h1_els = response.css("h1")
    if h1_els:
        t = _get_text(h1_els[0])
        if t:
            title = t.strip()

    if not title:
        # og:title fallback
        og_els = response.css('meta[property="og:title"]')
        if og_els:
            content = _get_attr(og_els[0], "content")
            if content:
                title = content.strip()

    return body_text, title


# ---------------------------------------------------------------------------
# URL classification
# ---------------------------------------------------------------------------
def _is_probable_video_url(url: str, debug: bool = False) -> bool:
    """Return True if *url* looks like a downloadable video link."""
    if not url:
        return False

    base = url.split("?")[0].lower()
    # Skip direct image files
    if base.endswith((".jpg", ".jpeg", ".png", ".gif", ".webp")):
        return False

    try:
        parsed = urlparse(url)
        netloc = (parsed.netloc or "").lower()
        path = (parsed.path or "").lower()
    except Exception:
        return False

    # Instagram — only post / reel / tv URLs
    if "instagram.com" in netloc:
        if path.startswith("/p/") or "/reel" in path or "/reels" in path or "/tv" in path:
            return True
        if debug:
            logger.debug("    Rejected Instagram URL (not a post/reel/tv): %s", url)
        return False

    # Facebook — only video paths
    if "facebook.com" in netloc or "fb.watch" in netloc:
        if "fb.watch" in netloc:
            return True
        if any(x in path for x in ("/video", "/videos", "/watch", "/video.php")):
            return True
        if debug:
            logger.debug("    Rejected Facebook URL (not a video): %s", url)
        return False

    # Common video hosts
    hosts = (
        "youtube.com", "youtu.be", "tiktok.com", "vimeo.com",
        "dailymotion.com", "x.com", "twitter.com",
    )
    if any(h in netloc for h in hosts):
        return True

    if debug:
        logger.debug("    Rejected host (not in whitelist): %s", url)
    return False


# ---------------------------------------------------------------------------
# Keyword matching helpers
# ---------------------------------------------------------------------------
def compile_keyword_patterns(
    keywords: Optional[List[str]],
    mode: str = "whole",
) -> List[tuple[str, re.Pattern[str]]]:
    """Pre-compile keyword regex patterns.

    Returns a list of ``(keyword_text, compiled_pattern)`` tuples.
    """
    if not keywords:
        return []

    flags = re.IGNORECASE
    patterns: List[tuple[str, re.Pattern[str]]] = []
    for kw in keywords:
        if mode == "whole":
            pat = re.compile(rf"(?<!\w){re.escape(kw)}(?!\w)", flags)
        else:
            pat = re.compile(re.escape(kw), flags)
        patterns.append((kw, pat))
    return patterns


def match_keywords(
    patterns: List[tuple[str, re.Pattern[str]]],
    fields: List[str],
) -> Optional[str]:
    """Return the first keyword that matches any of *fields*, or ``None``."""
    for kw, pat in patterns:
        for text in fields:
            if text and pat.search(text):
                return kw
    return None


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------
def _get_attr(element: Any, name: str) -> Optional[str]:
    """Safely get an attribute from a Scrapling Selector element."""
    # Scrapling: element.attrib is an AttributesHandler (dict-like)
    attrib = getattr(element, "attrib", None)
    if attrib and name in attrib:
        val = attrib[name]
        if isinstance(val, list):
            return " ".join(val)
        return str(val) if val else None
    return None


def _get_text(element: Any) -> str:
    """Safely extract text content from a Scrapling Selector element."""
    text = getattr(element, "text", None)
    if text is not None:
        return str(text).strip()
    # fallback: get_all_text
    fn = getattr(element, "get_all_text", None)
    if fn:
        return fn(strip=True) or ""
    return ""
