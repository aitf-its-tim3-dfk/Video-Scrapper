"""Configuration dataclass and CLI argument parsing."""
from __future__ import annotations

import argparse
import os
from dataclasses import dataclass, field
from typing import List, Literal, Optional


DEFAULT_BASE_LISTING_URL = "https://turnbackhoax.id/articles"

FetcherMode = Literal["http", "dynamic", "stealth"]


@dataclass
class ScrapeConfig:
    """All tunables for a scrape run, populated from CLI args or programmatically."""

    # --- Pagination ---
    start_page: int = 1
    end_page: int = 1
    category: str = "politik"
    base_url: str = DEFAULT_BASE_LISTING_URL

    # --- Output ---
    download_dir: str = "downloaded_videos"
    output_template: Optional[str] = None

    # --- Cookies ---
    cookies: Optional[str] = None
    confirm_cookies: bool = False
    cookies_from_browser: Optional[str] = None
    smart_cookies: bool = True  # Try without cookies first, retry on auth error

    # --- Delays ---
    min_delay_page: float = 2.0
    max_delay_page: float = 4.0
    min_delay_dl: float = 5.0
    max_delay_dl: float = 10.0

    # --- Filtering ---
    skip_no_audio: bool = False
    keywords: Optional[List[str]] = None
    keyword_mode: Literal["whole", "substring"] = "whole"
    keyword_field: Literal["body", "title", "both"] = "both"
    show_snippet: bool = False

    # --- Fetcher ---
    fetcher_mode: FetcherMode = "http"
    concurrency: int = 5
    user_agent: str = "Mozilla/5.0 (compatible; scraper/1.0; +https://example.com)"

    # --- Resumability ---
    checkpoint_file: Optional[str] = None
    resume: bool = False

    # --- Debugging ---
    debug: bool = False
    dry_run: bool = False
    log_level: str = "INFO"

    def __post_init__(self) -> None:
        if self.checkpoint_file is None:
            self.checkpoint_file = os.path.join(self.download_dir, "checkpoint.json")

    @property
    def use_cookies(self) -> bool:
        return bool(self.cookies) and bool(self.confirm_cookies)

    @property
    def use_cookies_from_browser(self) -> bool:
        return bool(self.cookies_from_browser)


def build_arg_parser() -> argparse.ArgumentParser:
    """Build the CLI argument parser."""
    p = argparse.ArgumentParser(
        description="Scrape TurnBackHoax listing pages and download embedded videos"
    )
    # Pagination
    p.add_argument("--start-page", type=int, default=1)
    p.add_argument("--end-page", type=int, default=1)
    p.add_argument("--category", default="politik")
    p.add_argument("--base-url", default=DEFAULT_BASE_LISTING_URL,
                   help="Base listing URL (used to build page links)")

    # Output
    p.add_argument("--download-dir", default="downloaded_videos")
    p.add_argument("--output", help="yt-dlp output template (e.g. '%%(title)s.%%(ext)s')")

    # Cookies
    p.add_argument("--cookies", help="Cookies file (Netscape format) for authenticated downloads")
    p.add_argument("--confirm-cookies", action="store_true",
                   help="Require explicit confirmation to use cookies")
    p.add_argument("--cookies-from-browser",
                   help="Pass cookies from browser to yt-dlp (e.g. 'chrome', 'firefox')")
    p.add_argument("--no-smart-cookies", action="store_true",
                   help="Disable smart cookies (always send cookies on every request)")

    # Delays
    p.add_argument("--min-delay-page", type=float, default=2.0,
                   help="Min delay between article requests")
    p.add_argument("--max-delay-page", type=float, default=4.0,
                   help="Max delay between article requests")
    p.add_argument("--min-delay-dl", type=float, default=5.0,
                   help="Min delay between downloads")
    p.add_argument("--max-delay-dl", type=float, default=10.0,
                   help="Max delay between downloads")

    # Filtering
    p.add_argument("--skip-no-audio", action="store_true",
                   help="Skip downloading items that probe as having no audio")
    p.add_argument("--keyword", action="append",
                   help="Keyword to filter articles (repeatable). Whole-word matching by default")
    p.add_argument("--keyword-mode", choices=("whole", "substring"), default="whole",
                   help="Keyword matching mode")
    p.add_argument("--keyword-field", choices=("body", "title", "both"), default="both",
                   help="Which field(s) to search for keywords")
    p.add_argument("--show-snippet", action="store_true",
                   help="Include a short snippet around matched keyword in CSV")

    # Fetcher
    p.add_argument("--fetcher-mode", choices=("http", "dynamic", "stealth"), default="http",
                   help="Scrapling fetcher mode: http (fast), dynamic (JS rendering), stealth (anti-bot)")
    p.add_argument("--concurrency", type=int, default=5,
                   help="Max concurrent article fetches")
    p.add_argument("--user-agent",
                   default="Mozilla/5.0 (compatible; scraper/1.0; +https://example.com)")

    # Resumability
    p.add_argument("--checkpoint-file",
                   help="Path to JSON checkpoint file (default: <download_dir>/checkpoint.json)")
    p.add_argument("--resume", action="store_true",
                   help="Resume from last checkpoint")

    # Debugging
    p.add_argument("--debug", action="store_true",
                   help="Enable debug logging for URL filtering and detection")
    p.add_argument("--dry-run", action="store_true",
                   help="Do everything except actually run yt-dlp downloads")
    p.add_argument("--log-level", default="INFO",
                   choices=("DEBUG", "INFO", "WARNING", "ERROR"),
                   help="Logging verbosity")

    return p


def parse_args(argv: Optional[List[str]] = None) -> ScrapeConfig:
    """Parse CLI arguments and return a :class:`ScrapeConfig`."""
    p = build_arg_parser()
    args = p.parse_args(argv)

    return ScrapeConfig(
        start_page=args.start_page,
        end_page=args.end_page,
        category=args.category,
        base_url=args.base_url,
        download_dir=args.download_dir,
        output_template=args.output,
        cookies=args.cookies,
        confirm_cookies=args.confirm_cookies,
        cookies_from_browser=args.cookies_from_browser,
        smart_cookies=not args.no_smart_cookies,
        min_delay_page=args.min_delay_page,
        max_delay_page=args.max_delay_page,
        min_delay_dl=args.min_delay_dl,
        max_delay_dl=args.max_delay_dl,
        skip_no_audio=args.skip_no_audio,
        keywords=args.keyword,
        keyword_mode=args.keyword_mode,
        keyword_field=args.keyword_field,
        show_snippet=args.show_snippet,
        fetcher_mode=args.fetcher_mode,
        concurrency=args.concurrency,
        user_agent=args.user_agent,
        checkpoint_file=args.checkpoint_file,
        resume=args.resume,
        debug=args.debug,
        dry_run=args.dry_run,
        log_level=args.log_level,
    )
