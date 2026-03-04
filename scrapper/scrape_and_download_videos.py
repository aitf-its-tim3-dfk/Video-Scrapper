#!/usr/bin/env python3
"""Scrape TurnBackHoax article listing pages, detect embedded video links
(TikTok, YouTube, Facebook), and download found videos using yt-dlp with
polite rate-limiting and a safe cookie mode.

This file is a thin wrapper around the ``turnbackhoax`` package which
contains the modular implementation.  All original CLI flags are preserved
and several new ones have been added:

  --fetcher-mode {http,dynamic,stealth}   Scrapling fetcher backend
  --concurrency N                         Max concurrent article fetches
  --checkpoint-file PATH                  JSON checkpoint for resume
  --resume                                Resume from last checkpoint

Usage examples:
  python scrape_and_download_videos.py --start-page 1 --end-page 3
  python scrape_and_download_videos.py --start-page 1 --end-page 1 \\
      --category politik --download-dir videos --fetcher-mode stealth \\
      --concurrency 3 --resume
"""
from __future__ import annotations

import os
import sys

# Ensure the parent directory (scrapper/) is on sys.path so the
# turnbackhoax package can be imported when this script is invoked directly.
_HERE = os.path.dirname(os.path.abspath(__file__))
if _HERE not in sys.path:
    sys.path.insert(0, _HERE)

from turnbackhoax.cli import main  # noqa: E402

if __name__ == "__main__":
    main()
