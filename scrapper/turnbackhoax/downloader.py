"""yt-dlp video download logic."""
from __future__ import annotations

import asyncio
import logging
import os
import random
import shlex
import subprocess
import sys
import time
from typing import Any, Dict, Iterable, List, Optional

import turnbackhoax  # noqa: F401 — triggers __init__.py which puts scrapper/ on sys.path
from ytdlp_utils import AUTH_ERROR_PATTERNS, is_auth_error

logger = logging.getLogger(__name__)


def is_format_error(error_msg: str) -> bool:
    """Detect if error is about format selection/availability."""
    error_lower = error_msg.lower()
    return any(p in error_lower for p in [
        'requested format is not available',
        'format not available',
        'no video formats found',
        'unable to extract video data',
    ])


# ---------------------------------------------------------------------------
# Command builder
# ---------------------------------------------------------------------------
def build_yt_dlp_cmd(
    url: str,
    download_dir: str,
    output_template: Optional[str],
    cookies: Optional[str],
    cookies_from_browser: Optional[str],
    chosen_format: Optional[str] = None,
) -> List[str]:
    """Build the ``yt-dlp`` CLI command list."""
    cmd = [sys.executable, "-m", "yt_dlp", url, "--no-playlist", "--retries", "10"]
    
    # Restrict filenames for Windows compatibility
    cmd.append("--restrict-filenames")

    if download_dir:
        os.makedirs(download_dir, exist_ok=True)
        # Limit title length to 100 chars (use .100B for bytes, safer for Unicode)
        outtmpl = output_template or "%(title).100B.%(ext)s"
        cmd += ["-o", os.path.join(download_dir, outtmpl)]
    elif output_template:
        cmd += ["-o", output_template]

    if cookies:
        cmd += ["--cookies", cookies]
    if cookies_from_browser:
        cmd += ["--cookies-from-browser", cookies_from_browser]

    if chosen_format:
        cmd += ["-f", chosen_format]

    return cmd


# ---------------------------------------------------------------------------
# Single-URL download (with smart cookie support)
# ---------------------------------------------------------------------------
def _download_one(
    url: str,
    download_dir: str,
    output_template: Optional[str],
    cookies: Optional[str],
    cookies_from_browser: Optional[str],
    chosen_format: Optional[str] = None,
    smart_cookies: bool = True,
    dry_run: bool = False,
) -> Dict[str, Any]:
    """Download a single URL, optionally using the smart-cookie strategy.

    Returns a dict with keys ``success``, ``auth_used``, and optionally
    ``error``.
    """
    if dry_run:
        logger.info("Dry-run enabled; skipping actual download")
        return {"success": True, "auth_used": False}

    has_cookies = bool(cookies or cookies_from_browser)

    # ------------------------------------------------------------------
    # Smart-cookie path: try without cookies first
    # ------------------------------------------------------------------
    if smart_cookies and has_cookies:
        cmd_no_auth = build_yt_dlp_cmd(
            url, download_dir, output_template,
            cookies=None, cookies_from_browser=None,
            chosen_format=chosen_format,
        )
        logger.debug("Smart-cookies: trying without auth — %s", url[:80])
        proc = subprocess.run(cmd_no_auth, capture_output=True, text=True)

        if proc.returncode == 0:
            return {"success": True, "auth_used": False}

        error_msg = proc.stderr.strip() if proc.stderr else f"Exit code {proc.returncode}"

        # Check for auth errors
        if is_auth_error(error_msg):
            logger.info("  Auth error detected, retrying WITH cookies — %s", url[:80])
            cmd_auth = build_yt_dlp_cmd(
                url, download_dir, output_template,
                cookies=cookies,
                cookies_from_browser=cookies_from_browser,
                chosen_format=chosen_format,
            )
            proc2 = subprocess.run(cmd_auth, capture_output=True, text=True)
            if proc2.returncode == 0:
                return {"success": True, "auth_used": True}
            error_msg2 = proc2.stderr.strip() if proc2.stderr else f"Exit code {proc2.returncode}"
            
            # Check if format error when using cookies
            if chosen_format and is_format_error(error_msg2):
                logger.info("  Format error with cookies, retrying without format selector — %s", url[:80])
                cmd_no_fmt = build_yt_dlp_cmd(
                    url, download_dir, output_template,
                    cookies=cookies,
                    cookies_from_browser=cookies_from_browser,
                    chosen_format=None,  # Let yt-dlp auto-select
                )
                proc3 = subprocess.run(cmd_no_fmt, capture_output=True, text=True)
                if proc3.returncode == 0:
                    return {"success": True, "auth_used": True}
                error_msg2 = proc3.stderr.strip() if proc3.stderr else f"Exit code {proc3.returncode}"
            
            return {"success": False, "auth_used": True, "error": error_msg2}

        # Check for format errors (non-auth)
        if chosen_format and is_format_error(error_msg):
            logger.info("  Format error detected, retrying without format selector — %s", url[:80])
            cmd_no_fmt = build_yt_dlp_cmd(
                url, download_dir, output_template,
                cookies=None, cookies_from_browser=None,
                chosen_format=None,  # Let yt-dlp auto-select
            )
            proc2 = subprocess.run(cmd_no_fmt, capture_output=True, text=True)
            if proc2.returncode == 0:
                return {"success": True, "auth_used": False}
            error_msg = proc2.stderr.strip() if proc2.stderr else f"Exit code {proc2.returncode}"

        # Non-auth, non-format error — cookies won't help
        return {"success": False, "auth_used": False, "error": error_msg}

    # ------------------------------------------------------------------
    # Normal path: use cookies if provided
    # ------------------------------------------------------------------
    cmd = build_yt_dlp_cmd(
        url, download_dir, output_template,
        cookies=cookies if has_cookies else None,
        cookies_from_browser=cookies_from_browser if has_cookies else None,
        chosen_format=chosen_format,
    )
    logger.info("Running: %s", " ".join(shlex.quote(p) for p in cmd))

    proc = subprocess.run(cmd, capture_output=True, text=True)
    if proc.returncode == 0:
        return {"success": True, "auth_used": has_cookies}
    
    error_msg = proc.stderr.strip() if proc.stderr else f"Exit code {proc.returncode}"
    
    # Check for format error in normal path
    if chosen_format and is_format_error(error_msg):
        logger.info("  Format error detected, retrying without format selector — %s", url[:80])
        cmd_no_fmt = build_yt_dlp_cmd(
            url, download_dir, output_template,
            cookies=cookies if has_cookies else None,
            cookies_from_browser=cookies_from_browser if has_cookies else None,
            chosen_format=None,  # Let yt-dlp auto-select
        )
        proc2 = subprocess.run(cmd_no_fmt, capture_output=True, text=True)
        if proc2.returncode == 0:
            return {"success": True, "auth_used": has_cookies}
        error_msg = proc2.stderr.strip() if proc2.stderr else f"Exit code {proc2.returncode}"
    
    return {"success": False, "auth_used": has_cookies, "error": error_msg}


# ---------------------------------------------------------------------------
# Batch download
# ---------------------------------------------------------------------------
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
    smart_cookies: bool = True,
) -> int:
    """Download a list of video items using yt-dlp.

    *items*: Iterable of strings (URLs) or dicts with keys ``url`` and
    optional ``chosen_format``.

    When *smart_cookies* is True and cookies are configured, each download
    first attempts **without** cookies.  If that fails with an
    authentication error the download is retried **with** cookies.

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

    # Resolve effective cookie values
    eff_cookies = cookies if use_cookies else None
    eff_cookies_browser = cookies_from_browser if use_cookies_from_browser else None

    success_count = 0
    for i, entry in enumerate(normalised, start=1):
        url = entry["url"]
        fmt = entry.get("chosen_format")
        logger.info("[%d/%d] Downloading: %s", i, len(normalised), url)
        if fmt:
            logger.info("  -> using format: %s", fmt)

        result = _download_one(
            url,
            download_dir=download_dir,
            output_template=output_template,
            cookies=eff_cookies,
            cookies_from_browser=eff_cookies_browser,
            chosen_format=fmt,
            smart_cookies=smart_cookies,
            dry_run=dry_run,
        )

        if result["success"]:
            auth_tag = " (with cookies)" if result.get("auth_used") else " (no cookies)"
            logger.info("  ✓ Downloaded%s", auth_tag)
            success_count += 1
        else:
            logger.error("  ✗ Failed: %s", result.get("error", "unknown"))

        # Delay between downloads (skip after last)
        if i < len(normalised):
            delay = random.uniform(min_delay, max_delay)
            logger.info("Sleeping %.1fs before next download...", delay)
            time.sleep(delay)

    return success_count


# ---------------------------------------------------------------------------
# Async concurrent batch download
# ---------------------------------------------------------------------------
async def download_videos_async(
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
    smart_cookies: bool = True,
    concurrency: int = 2,
) -> int:
    """Concurrent version of :func:`download_videos`.

    Runs up to *concurrency* yt-dlp subprocesses in parallel using a thread
    pool executor, with a randomised politeness delay after each download.
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

    eff_cookies = cookies if use_cookies else None
    eff_cookies_browser = cookies_from_browser if use_cookies_from_browser else None

    sem = asyncio.Semaphore(concurrency)
    loop = asyncio.get_running_loop()
    success_count = 0
    count_lock = asyncio.Lock()

    async def _dl(i: int, entry: Dict[str, Any]) -> None:
        nonlocal success_count
        async with sem:
            url = entry["url"]
            fmt = entry.get("chosen_format")
            logger.info("[%d/%d] Downloading: %s", i, len(normalised), url)
            if fmt:
                logger.info("  -> using format: %s", fmt)

            result = await loop.run_in_executor(
                None,
                lambda: _download_one(
                    url,
                    download_dir=download_dir,
                    output_template=output_template,
                    cookies=eff_cookies,
                    cookies_from_browser=eff_cookies_browser,
                    chosen_format=fmt,
                    smart_cookies=smart_cookies,
                    dry_run=dry_run,
                ),
            )

            if result["success"]:
                auth_tag = " (with cookies)" if result.get("auth_used") else " (no cookies)"
                logger.info("  ✓ Downloaded%s: %s", auth_tag, url)
                async with count_lock:
                    success_count += 1
            else:
                logger.error("  ✗ Failed: %s — %s", url, result.get("error", "unknown"))

            await asyncio.sleep(random.uniform(min_delay, max_delay))

    await asyncio.gather(*[_dl(i, e) for i, e in enumerate(normalised, 1)])
    return success_count
