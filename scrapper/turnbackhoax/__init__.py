"""turnbackhoax — Modular async scraper for TurnBackHoax article videos.

This package uses Scrapling (vendored at scrapper/Scrapling/) for fetching and
HTML parsing, and yt-dlp for video probing and downloading.
"""
from __future__ import annotations

import os
import sys

# ---------------------------------------------------------------------------
# Vendored Scrapling path setup
# ---------------------------------------------------------------------------
# The Scrapling library lives alongside this package at:
#   <repo>/scrapper/Scrapling/
# We add it to sys.path so ``from scrapling import ...`` works without a pip
# install.  The path is resolved relative to *this* file so it doesn't matter
# where the user's CWD is.
_SCRAPPER_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_SCRAPLING_ROOT = os.path.join(_SCRAPPER_DIR, "Scrapling")
if _SCRAPLING_ROOT not in sys.path:
    sys.path.insert(0, _SCRAPLING_ROOT)

__version__ = "0.1.0"
