"""JSON-based checkpoint system for resumable scraping."""
from __future__ import annotations

import json
import logging
import os
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Set

logger = logging.getLogger(__name__)


@dataclass
class CheckpointState:
    """In-memory representation of a scrape checkpoint."""

    last_page: int = 0
    last_article_index: int = 0
    processed_articles: Set[str] = field(default_factory=set)
    found_videos: List[Dict[str, Any]] = field(default_factory=list)
    skipped_items: List[Dict[str, Any]] = field(default_factory=list)

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------
    def is_article_processed(self, url: str) -> bool:
        return url in self.processed_articles

    def mark_article_processed(self, url: str) -> None:
        self.processed_articles.add(url)

    def add_video(self, video: Dict[str, Any]) -> None:
        # deduplicate by URL
        if not any(v.get("url") == video.get("url") for v in self.found_videos):
            self.found_videos.append(video)

    def add_skipped(self, item: Dict[str, Any]) -> None:
        self.skipped_items.append(item)


def load_checkpoint(path: str) -> CheckpointState:
    """Load checkpoint from *path*.  Returns a fresh state if file is missing."""
    if not os.path.exists(path):
        logger.info("No checkpoint file at %s — starting fresh", path)
        return CheckpointState()

    try:
        with open(path, "r", encoding="utf-8") as fh:
            data = json.load(fh)
    except (json.JSONDecodeError, OSError) as exc:
        logger.warning("Failed to read checkpoint %s: %s — starting fresh", path, exc)
        return CheckpointState()

    logger.info(
        "Resuming from checkpoint: page=%d, article_idx=%d, %d articles processed, "
        "%d videos found, %d skipped",
        data.get("last_page", 0),
        data.get("last_article_index", 0),
        len(data.get("processed_articles", [])),
        len(data.get("found_videos", [])),
        len(data.get("skipped_items", [])),
    )

    return CheckpointState(
        last_page=data.get("last_page", 0),
        last_article_index=data.get("last_article_index", 0),
        processed_articles=set(data.get("processed_articles", [])),
        found_videos=list(data.get("found_videos", [])),
        skipped_items=list(data.get("skipped_items", [])),
    )


def save_checkpoint(path: str, state: CheckpointState) -> None:
    """Persist *state* to *path* as JSON.  Creates parent dirs as needed."""
    parent = os.path.dirname(path)
    if parent:
        os.makedirs(parent, exist_ok=True)

    payload = {
        "last_page": state.last_page,
        "last_article_index": state.last_article_index,
        "processed_articles": sorted(state.processed_articles),
        "found_videos": state.found_videos,
        "skipped_items": state.skipped_items,
    }

    tmp = path + ".tmp"
    try:
        with open(tmp, "w", encoding="utf-8") as fh:
            json.dump(payload, fh, indent=2, ensure_ascii=False)
        # atomic-ish rename (works on Windows if target doesn't exist or
        # on Python 3.12+ with os.replace)
        if os.path.exists(path):
            os.remove(path)
        os.rename(tmp, path)
        logger.debug("Checkpoint saved to %s", path)
    except OSError as exc:
        logger.error("Failed to save checkpoint to %s: %s", path, exc)
        # try to clean up temp file
        if os.path.exists(tmp):
            try:
                os.remove(tmp)
            except OSError:
                pass
