"""CSV export functions for scrape results."""
from __future__ import annotations

import csv
import logging
import os
from typing import Any, Dict, List

logger = logging.getLogger(__name__)

# Shared header for video CSV files
VIDEO_CSV_HEADER = [
    "no", "video_name", "link_article", "link_video_asli",
    "has_audio", "category", "matched_keyword", "snippet",
]

SKIPPED_CSV_HEADER = [
    "no", "article", "link_video_asli", "reason",
    "detail", "category", "matched_keyword",
]


def _write_csv(
    path: str,
    header: List[str],
    rows: List[List[Any]],
) -> None:
    """Write *rows* to a CSV at *path* with *header*."""
    parent = os.path.dirname(path)
    if parent:
        os.makedirs(parent, exist_ok=True)
    with open(path, "w", encoding="utf-8", newline="") as fh:
        writer = csv.writer(fh)
        writer.writerow(header)
        writer.writerows(rows)
    logger.info("Wrote %d rows to %s", len(rows), path)


def write_video_index(
    download_dir: str,
    videos: List[Dict[str, Any]],
    filename: str = "video_index.csv",
) -> str:
    """Write the full video index CSV.  Returns the output path."""
    path = os.path.join(download_dir, filename)
    rows = [
        [
            i,
            item.get("title") or "",
            item.get("article", ""),
            item.get("url", ""),
            bool(item.get("has_audio")),
            item.get("category", ""),
            item.get("matched_keyword", ""),
            item.get("snippet", ""),
        ]
        for i, item in enumerate(videos, start=1)
    ]
    _write_csv(path, VIDEO_CSV_HEADER, rows)
    return path


def write_extracted_videos(
    download_dir: str,
    videos: List[Dict[str, Any]],
    filename: str = "extracted_videos.csv",
) -> str:
    """Write the extracted (probe-OK) videos CSV.  Returns the output path."""
    extracted = [v for v in videos if not v.get("probe_error")]
    if not extracted:
        logger.info("No extracted videos to write.")
        return ""
    path = os.path.join(download_dir, filename)
    rows = [
        [
            i,
            item.get("title") or "",
            item.get("article", ""),
            item.get("url", ""),
            bool(item.get("has_audio")),
            item.get("category", ""),
            item.get("matched_keyword", ""),
            item.get("snippet", ""),
        ]
        for i, item in enumerate(extracted, start=1)
    ]
    _write_csv(path, VIDEO_CSV_HEADER, rows)
    return path


def write_skipped_items(
    download_dir: str,
    skipped: List[Dict[str, Any]],
    filename: str = "skipped_items.csv",
) -> str:
    """Write the skipped-items CSV.  Returns the output path."""
    if not skipped:
        logger.info("No skipped items to write.")
        return ""
    path = os.path.join(download_dir, filename)
    rows = [
        [
            i,
            s.get("article", ""),
            s.get("url", ""),
            s.get("reason", ""),
            s.get("detail", ""),
            s.get("category", ""),
            s.get("matched_keyword", ""),
        ]
        for i, s in enumerate(skipped, start=1)
    ]
    _write_csv(path, SKIPPED_CSV_HEADER, rows)
    return path
