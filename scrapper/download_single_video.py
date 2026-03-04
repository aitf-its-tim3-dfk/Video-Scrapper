#!/usr/bin/env python3
"""
Simple Facebook video downloader using yt-dlp.

Usage:
  python download_facebook_video.py <URL> [--output OUTPUT] [--cookies COOKIES]

Examples:
  python download_facebook_video.py https://www.facebook.com/.../videos/12345/
  python download_facebook_video.py <URL> --output "C:/Videos/%(title)s.%(ext)s"
  python download_facebook_video.py <URL> --cookies cookies.txt

Notes:
- If `yt-dlp` isn't installed the script will try to install it with pip.
- For private videos you must provide a cookies file exported from your browser
  (Netscape/Mozilla format) and pass it with --cookies.
"""
from __future__ import annotations

import argparse
import os
import random
import shutil
import subprocess
import sys
import time
from typing import Iterable, List, Optional


def ensure_yt_dlp() -> None:
    """Ensure yt_dlp is importable. Try to install it if missing."""
    try:
        import yt_dlp  # noqa: F401
        return
    except Exception:
        print("yt-dlp not found, attempting to install via pip...")
        cmd = [sys.executable, "-m", "pip", "install", "--upgrade", "yt-dlp"]
        try:
            subprocess.check_call(cmd)
        except subprocess.CalledProcessError as e:
            print("Failed to install yt-dlp. Please install it manually:")
            print("  python -m pip install --upgrade yt-dlp")
            raise SystemExit(1)


def download_video(url: str, output: Optional[str] = None, cookies: Optional[str] = None) -> None:
    ensure_yt_dlp()
    from yt_dlp import YoutubeDL

    # choose format: prefer separate best video+audio when ffmpeg is available,
    # otherwise fall back to a single-file `best` format to avoid merge errors.
    ffmpeg_present = shutil.which("ffmpeg") is not None
    if not ffmpeg_present:
        print("Warning: ffmpeg not found in PATH. The downloader will request a single combined format to avoid merging errors.")
        print("To enable best-quality merging (video+audio), install ffmpeg and ensure it is on your PATH.")
    ydl_opts = {
        # write to given output template or default to title
        "outtmpl": output or "%(title)s.%(ext)s",
        # prefer separate best video+audio when ffmpeg is available
        "format": "bestvideo+bestaudio/best" if ffmpeg_present else "best",
        "noplaylist": True,
        "continuedl": True,
        "retries": 10,
        "quiet": False,
        "no_warnings": True,
    }

    if cookies:
        if not os.path.exists(cookies):
            print(f"Warning: cookies file '{cookies}' not found. Continuing without cookies.")
        else:
            ydl_opts["cookiefile"] = cookies

    print(f"Downloading: {url}")
    with YoutubeDL(ydl_opts) as ydl:
        ydl.download([url])


def download_many(urls: Iterable[str], output: Optional[str] = None, cookies: Optional[str] = None,
                  min_delay: float = 5.0, max_delay: float = 10.0) -> None:
    """Download multiple URLs with randomized delays between downloads."""
    urls_list: List[str] = [u for u in (u.strip() for u in urls) if u]
    for i, u in enumerate(urls_list, start=1):
        print(f"\n[{i}/{len(urls_list)}] Processing: {u}")
        try:
            download_video(u, output, cookies)
        except Exception as exc:
            print(f"Download failed for {u}: {exc}")
        if i < len(urls_list):
            delay = random.uniform(min_delay, max_delay)
            print(f"Sleeping for {delay:.1f}s before next download...")
            time.sleep(delay)


def main(argv: Optional[list[str]] = None) -> None:
    p = argparse.ArgumentParser(description="Download Facebook video using yt-dlp")
    p.add_argument("url", help="Facebook video URL")
    p.add_argument("--output", "-o", help="Output template (yt-dlp style)")
    p.add_argument("--cookies", "-c", help="Cookies file (Netscape format) for private videos")
    args = p.parse_args(argv)

    try:
        download_video(args.url, args.output, args.cookies)
    except Exception as exc:
        print("Download failed:", exc)
        sys.exit(2)


if __name__ == "__main__":
    main()
