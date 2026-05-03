"""yt-dlp video probing — extract metadata without downloading."""
from __future__ import annotations

import logging
import shutil
import subprocess
import sys
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)


def ensure_yt_dlp() -> None:
    """Make sure yt_dlp is importable.  Installs via pip if missing."""
    try:
        import yt_dlp  # noqa: F401
    except Exception:
        logger.info("yt-dlp not found, installing...")
        subprocess.check_call(
            [sys.executable, "-m", "pip", "install", "--upgrade", "yt-dlp"]
        )


def probe_video(
    url: str,
    timeout: float = 30.0,
    cookiefile: Optional[str] = None,
    cookies_from_browser: Optional[str] = None,
) -> Dict[str, Any]:
    """Probe a video URL using yt-dlp Python API and return metadata.

    Returns a dict with keys:
    ``has_audio``, ``has_combined``, ``recommended_format``, ``title``,
    and optionally ``error``.
    """
    try:
        from yt_dlp import YoutubeDL
    except Exception:
        logger.warning("yt-dlp not available for probe")
        return {
            "has_audio": False,
            "has_combined": False,
            "recommended_format": None,
            "title": None,
        }

    ydl_opts: Dict[str, Any] = {
        "skip_download": True,
        "quiet": True,
        "no_warnings": True,
        "socket_timeout": timeout,
    }
    if cookiefile:
        ydl_opts["cookiefile"] = cookiefile
    if cookies_from_browser:
        ydl_opts["cookiesfrombrowser"] = cookies_from_browser

    try:
        with YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=False)
    except Exception as exc:
        msg = str(exc)
        logger.warning("yt-dlp probe failed for %s: %s", url, msg)
        return {
            "error": msg,
            "has_audio": False,
            "has_combined": False,
            "recommended_format": None,
            "title": None,
        }

    # Analyse formats
    formats = info.get("formats") or []
    has_audio = False
    has_combined = False

    for f in formats:
        ac = f.get("acodec")
        vc = f.get("vcodec")
        proto = (f.get("protocol") or "").lower()
        abr = f.get("abr")
        asr = f.get("asr")

        if ac and ac != "none":
            has_audio = True
        if ac and ac != "none" and vc and vc != "none":
            has_combined = True
        # HLS/DASH manifests may not always set acodec on format entries;
        # conservatively assume audio is present.
        if proto and any(x in proto for x in ("m3u8", "hls", "dash", "f4m")):
            has_audio = True

    # Top-level acodec check
    top_ac = info.get("acodec")
    if top_ac and top_ac != "none":
        has_audio = True

    ffmpeg_present = shutil.which("ffmpeg") is not None
    if has_audio:
        recommended = "bestvideo+bestaudio/best" if ffmpeg_present else "best"
    else:
        recommended = "bestvideo"

    title = info.get("title")
    description = info.get("description") or ""
    # Flatten newlines to single spaces, same as reference script
    caption = " ".join(description.replace("\r", " ").split()).strip()

    return {
        "has_audio": has_audio,
        "has_combined": has_combined,
        "recommended_format": recommended,
        "title": title,
        "caption_post": caption,
    }
