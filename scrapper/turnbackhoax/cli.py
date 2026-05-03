"""CLI entry point for the turnbackhoax scraper."""
from __future__ import annotations

import asyncio
import logging
import sys
from typing import List, Optional

from turnbackhoax.config import parse_args
from turnbackhoax.prober import ensure_yt_dlp
from turnbackhoax.runner import scrape_pages_and_download


def main(argv: Optional[List[str]] = None) -> None:
    """Parse CLI arguments and launch the async scrape pipeline."""
    ensure_yt_dlp()
    config = parse_args(argv)

    logging.basicConfig(
        level=getattr(logging, config.log_level),
        format="%(asctime)s [%(levelname)s] %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    try:
        asyncio.run(scrape_pages_and_download(config))
    except KeyboardInterrupt:
        logging.getLogger(__name__).info("Interrupted by user.")
        sys.exit(130)


if __name__ == "__main__":
    main()
