"""CSV export functions for scrape results."""
from __future__ import annotations

import csv
import logging
import os
from typing import Any, Dict, List

logger = logging.getLogger(__name__)

# Shared header for video CSV files
VIDEO_CSV_HEADER = [
    "no", "video_name", "filename", "link_article", "article_title", "link_video_asli",
    "has_audio", "category", "matched_keyword", "snippet",
    "date", "author", "image_url", "caption_post",
    "narasi", "penjelasan", "kesimpulan",
    "factcheck_result", "factcheck_source", "references",
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
            item.get("filename") or "",
            item.get("article", ""),
            item.get("article_title", ""),
            item.get("url", ""),
            bool(item.get("has_audio")),
            item.get("category", ""),
            item.get("matched_keyword", ""),
            item.get("snippet", ""),
            item.get("date", ""),
            item.get("author", ""),
            item.get("image_url", ""),
            item.get("caption_post", ""),
            item.get("narasi", ""),
            item.get("penjelasan", ""),
            item.get("kesimpulan", ""),
            item.get("factcheck_result", ""),
            item.get("factcheck_source", ""),
            "; ".join(item.get("references", [])) if item.get("references") else "",
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
            item.get("filename") or "",
            item.get("article", ""),
            item.get("article_title", ""),
            item.get("url", ""),
            bool(item.get("has_audio")),
            item.get("category", ""),
            item.get("matched_keyword", ""),
            item.get("snippet", ""),
            item.get("date", ""),
            item.get("author", ""),
            item.get("image_url", ""),
            item.get("caption_post", ""),
            item.get("narasi", ""),
            item.get("penjelasan", ""),
            item.get("kesimpulan", ""),
            item.get("factcheck_result", ""),
            item.get("factcheck_source", ""),
            "; ".join(item.get("references", [])) if item.get("references") else "",
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


def write_downloaded_videos(
    download_dir: str,
    videos: List[Dict[str, Any]],
    filename: str = "downloaded_videos.csv",
) -> str:
    """Write CSV with only videos that physically exist in the download directory.
    
    This function verifies that the video file actually exists on disk before
    including it in the CSV output.
    
    Returns the output path.
    """
    # Filter videos that have a title (filename) and the file actually exists
    downloaded = []
    for v in videos:
        video_name = v.get("title")
        if not video_name:
            continue
        
        # Check if the video file exists in the download directory
        video_path = os.path.join(download_dir, video_name)
        if os.path.isfile(video_path):
            # Verify it's actually a video file by checking extension
            ext = os.path.splitext(video_name)[1].lower()
            if ext in [".mp4", ".mkv", ".webm", ".mov", ".avi", ".flv", ".m4v", ".ts"]:
                downloaded.append(v)
            else:
                logger.debug("Skipping non-video file: %s", video_name)
        else:
            logger.debug("Video file not found on disk: %s", video_path)
    
    if not downloaded:
        logger.info("No downloaded videos found in directory.")
        return ""
    
    path = os.path.join(download_dir, filename)
    rows = [
        [
            i,
            item.get("title") or "",
            item.get("filename") or "",
            item.get("article", ""),
            item.get("article_title", ""),
            item.get("url", ""),
            bool(item.get("has_audio")),
            item.get("category", ""),
            item.get("matched_keyword", ""),
            item.get("snippet", ""),
            item.get("date", ""),
            item.get("author", ""),
            item.get("image_url", ""),
            item.get("caption_post", ""),
            item.get("narasi", ""),
            item.get("penjelasan", ""),
            item.get("kesimpulan", ""),
            item.get("factcheck_result", ""),
            item.get("factcheck_source", ""),
            "; ".join(item.get("references", [])) if item.get("references") else "",
        ]
        for i, item in enumerate(downloaded, start=1)
    ]
    _write_csv(path, VIDEO_CSV_HEADER, rows)
    logger.info("Found %d videos physically present in %s", len(downloaded), download_dir)
    return path
