"""yt-dlp video download logic."""
from __future__ import annotations

import logging
import os
import random
import shlex
import subprocess
import sys
import time
from typing import Any, Dict, Iterable, List, Optional

logger = logging.getLogger(__name__)


def build_yt_dlp_cmd(
    url: str,
    download_dir: str,
    output_template: Optional[str],
    cookies: Optional[str],
    use_cookies: bool,
    cookies_from_browser: Optional[str],
    use_cookies_from_browser: bool,
) -> List[str]:
    """Build the ``yt-dlp`` CLI command list."""
    cmd = [sys.executable, "-m", "yt_dlp", url, "--no-playlist", "--retries", "10"]

    if download_dir:
        os.makedirs(download_dir, exist_ok=True)
        outtmpl = output_template or "%(title)s.%(ext)s"
        cmd += ["-o", os.path.join(download_dir, outtmpl)]
    elif output_template:
        cmd += ["-o", output_template]

    if use_cookies and cookies:
        cmd += ["--cookies", cookies]
    if use_cookies_from_browser and cookies_from_browser:
        cmd += ["--cookies-from-browser", cookies_from_browser]

    return cmd


def download_videos(
    items: Iterable[Any],
    download_dir: str,
    output_template: Optional[str],
    cookies: Optional[str],
    use_cookies: bool,
    min_delay: float = 5.0,
    max_delay: float = 10.0,
    dry_run: bool = False,
    cookies_from_browser: Optional[str] = None,
    use_cookies_from_browser: bool = False,
) -> int:
    """Download a list of video items using yt-dlp.

    *items*: Iterable of strings (URLs) or dicts with keys ``url`` and
    optional ``chosen_format``.

    Returns the number of successful downloads.
    """
    normalised: List[Dict[str, Any]] = []
    for item in items:
        if isinstance(item, str):
            normalised.append({"url": item, "chosen_format": None})
        elif isinstance(item, dict):
            normalised.append({
                "url": item.get("url"),
                "chosen_format": item.get("chosen_format"),
            })
        else:
            continue

    success_count = 0
    for i, entry in enumerate(normalised, start=1):
        url = entry["url"]
        fmt = entry.get("chosen_format")
        logger.info("[%d/%d] Downloading: %s", i, len(normalised), url)

        cmd = build_yt_dlp_cmd(
            url, download_dir, output_template, cookies, use_cookies,
            cookies_from_browser, use_cookies_from_browser,
        )
        if fmt:
            cmd += ["-f", fmt]
            logger.info("  -> using format: %s", fmt)

        logger.info("Running: %s", " ".join(shlex.quote(p) for p in cmd))

        try:
            if dry_run:
                logger.info("Dry-run enabled; skipping actual download")
                success_count += 1
            else:
                subprocess.check_call(cmd)
                success_count += 1
        except subprocess.CalledProcessError as exc:
            logger.error("yt-dlp failed for %s: %s", url, exc)

        # Delay between downloads (skip after last)
        if i < len(normalised):
            delay = random.uniform(min_delay, max_delay)
            logger.info("Sleeping %.1fs before next download...", delay)
            time.sleep(delay)

    return success_count
