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
# Article metadata extraction
# ---------------------------------------------------------------------------
def extract_article_metadata(response: Any) -> Dict[str, Any]:
    """Extract comprehensive metadata from a TurnBackHoax article page.
    
    Returns a dict with keys:
        - title: str
        - date: str (format: DD/MM/YYYY or ISO)
        - category: str
        - author: str
        - image_url: str
        - narasi: str (full HTML/text)
        - penjelasan: str (full HTML/text)
        - kesimpulan: str
        - factcheck_result: str (e.g., "Salah", "Benar", etc.)
        - factcheck_source: str
        - references: List[str] (list of reference URLs)
    """
    metadata: Dict[str, Any] = {
        "title": None,
        "date": None,
        "category": None,
        "author": None,
        "image_url": None,
        "narasi": None,
        "penjelasan": None,
        "kesimpulan": None,
        "factcheck_result": None,
        "factcheck_source": None,
        "references": [],
    }
    
    # Extract title from h1
    h1_els = response.css("h1")
    if h1_els:
        metadata["title"] = _get_text(h1_els[0])
    
    # Extract date from <time> tag
    time_els = response.css("time[datetime]")
    if time_els:
        # Try datetime attribute first (ISO format)
        datetime_val = _get_attr(time_els[0], "datetime")
        if datetime_val:
            metadata["date"] = datetime_val
        else:
            # Fallback to visible text
            metadata["date"] = _get_text(time_els[0])
    
    # Extract category from article metadata section
    cat_links = response.css("p a.text-light-blue")
    if cat_links:
        metadata["category"] = _get_text(cat_links[0])
    
    # Extract author (usually "Mafindo" in the same paragraph as date)
    # Look for <span> after <time> in the same <p>
    author_spans = response.css("article p span")
    for span in author_spans:
        text = _get_text(span)
        if text and text not in ["Politik", "Kesehatan", "Teknologi"]:  # Skip categories
            # Check if it's not a date
            if not re.match(r"\d{2}/\d{2}/\d{4}", text):
                metadata["author"] = text
                break
    
    # Extract header image
    fig_imgs = response.css("figure img")
    if fig_imgs:
        metadata["image_url"] = _get_attr(fig_imgs[0], "src")
    
    # Extract Narasi (article-origin section)
    narasi_section = response.css("section.article-origin")
    if narasi_section:
        # Get the quoted div
        quoted_divs = narasi_section[0].css(".quoted")
        if quoted_divs:
            # Get text content (strip HTML for cleaner output)
            narasi_text = _get_text(quoted_divs[0])
            metadata["narasi"] = narasi_text.strip() if narasi_text else None
    
    # Extract Penjelasan (article-explanation section)
    penjelasan_sections = response.css("section.article-explanation")
    for section in penjelasan_sections:
        # Check the header
        strong_els = section.css("strong")
        if strong_els:
            header = _get_text(strong_els[0])
            if "Penjelasan" in header:
                # Get the content div after the strong tag
                content_divs = section.css("div")
                if content_divs:
                    penjelasan_text = _get_text(content_divs[0])
                    metadata["penjelasan"] = penjelasan_text.strip() if penjelasan_text else None
            elif "Kesimpulan" in header:
                # Get the content div after the strong tag
                content_divs = section.css("div")
                if content_divs:
                    kesimpulan_text = _get_text(content_divs[0])
                    metadata["kesimpulan"] = kesimpulan_text.strip() if kesimpulan_text else None
    
    # Extract Factcheck Result (article-factcheck section)
    factcheck_section = response.css("section.article-factcheck")
    if factcheck_section:
        # Get the rating (e.g., "Salah", "Benar")
        result_spans = factcheck_section[0].css("span.factcheck-result")
        if result_spans:
            metadata["factcheck_result"] = _get_text(result_spans[0])
        
        # Get the source
        source_spans = factcheck_section[0].css("span.factcheck-source a")
        if source_spans:
            metadata["factcheck_source"] = _get_attr(source_spans[0], "href")
    
    # Extract References (article-references section)
    ref_section = response.css("section.article-references")
    if ref_section:
        ref_links = ref_section[0].css("li a")
        metadata["references"] = [_get_attr(a, "href") for a in ref_links if _get_attr(a, "href")]
    
    return metadata


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

    # Facebook — video paths including Reels and share links
    if "facebook.com" in netloc or "fb.watch" in netloc:
        if "fb.watch" in netloc:
            return True
        if any(x in path for x in ("/video", "/videos", "/watch", "/video.php", "/share/r/", "/share/v/", "/reel", "/reels")):
            return True
        if debug:
            logger.debug("    Rejected Facebook URL (not a video): %s", url)
        return False

    # TikTok — only actual video URLs, NOT hashtag/tag/trending pages
    if "tiktok.com" in netloc:
        # Reject hashtag/tag/trending/explore pages
        if any(x in path for x in ("/tag/", "/hashtag/", "/trending", "/explore", "/discover")):
            if debug:
                logger.debug("    Rejected TikTok URL (hashtag/tag page): %s", url)
            return False
        # Accept video URLs (must contain /video/)
        if "/video/" in path or "/@" in path:
            return True
        if debug:
            logger.debug("    Rejected TikTok URL (not a video): %s", url)
        return False

    # Common video hosts
    hosts = (
        "youtube.com", "youtu.be", "vimeo.com",
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
    # Try get_all_text method first (most reliable for Scrapling)
    fn = getattr(element, "get_all_text", None)
    if fn and callable(fn):
        try:
            result = fn(strip=True)
            if result:
                return str(result)
        except Exception:
            pass
    
    # Fallback to text property
    text = getattr(element, "text", None)
    if text is not None:
        return str(text).strip()
    
    return ""


def _get_inner_html(element: Any) -> str:
    """Extract inner HTML from a Scrapling Selector element."""
    # Try to get the raw HTML
    if hasattr(element, "html"):
        return str(element.html)
    # Fallback to text
    return _get_text(element)
