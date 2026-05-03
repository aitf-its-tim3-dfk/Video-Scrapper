"""Async orchestrator — main scrape-and-download pipeline.

Replaces the monolithic ``scrape_pages_and_download()`` from the original
single-file script with a modular async implementation.
"""
from __future__ import annotations

import asyncio
import logging
import os
import random
import re
from typing import Any, Dict, List, Optional

from turnbackhoax.checkpoint import CheckpointState, load_checkpoint, save_checkpoint
from turnbackhoax.config import ScrapeConfig
from turnbackhoax.downloader import download_videos_async
from turnbackhoax.exporter import write_downloaded_videos, write_extracted_videos, write_skipped_items, write_video_index
from turnbackhoax.fetcher import FetchResult, fetch_many, fetch_page
from turnbackhoax.parser import (
    compile_keyword_patterns,
    detect_video_urls,
    extract_article_metadata,
    extract_article_text_and_title,
    find_article_links_from_listing,
    match_keywords,
)
from turnbackhoax.prober import probe_video

logger = logging.getLogger(__name__)


async def _probe_in_executor(
    url: str,
    cookiefile: Optional[str] = None,
    cookies_from_browser: Optional[str] = None,
) -> Dict[str, Any]:
    """Run the (blocking) yt-dlp probe in a thread-pool executor."""
    loop = asyncio.get_running_loop()
    return await loop.run_in_executor(
        None,
        lambda: probe_video(
            url,
            cookiefile=cookiefile,
            cookies_from_browser=cookies_from_browser,
        ),
    )


# ---------------------------------------------------------------------------
# Main pipeline
# ---------------------------------------------------------------------------
async def scrape_pages_and_download(config: ScrapeConfig) -> None:
    """Async entry point for the full scrape-and-download pipeline.

    1. Iterate listing pages
    2. Fetch articles concurrently (batched by ``config.concurrency``)
    3. Detect video URLs in each article
    4. Probe each video with yt-dlp (in executor)
    5. Checkpoint after every article
    6. Export CSV indexes
    7. Download videos with yt-dlp
    """
    # ── Load or create checkpoint ─────────────────────────────────────
    ckpt_path = config.checkpoint_file or "checkpoint.json"
    state: CheckpointState
    if config.resume:
        state = load_checkpoint(ckpt_path)
    else:
        state = CheckpointState()

    # Cookie helpers
    cookiefile = config.cookies if config.use_cookies else None
    cookies_browser = config.cookies_from_browser if config.use_cookies_from_browser else None

    if config.cookies and not config.confirm_cookies:
        logger.warning(
            "Cookies provided but --confirm-cookies not set.  "
            "Cookies will NOT be used.  Pass --confirm-cookies to enable."
        )

    # ── Pre-compile keyword patterns ──────────────────────────────────
    kw_patterns = compile_keyword_patterns(config.keywords, config.keyword_mode)

    # ── Page loop ─────────────────────────────────────────────────────
    for page in range(config.start_page, config.end_page + 1):
        # Resume support: skip pages already fully processed
        if config.resume and page < state.last_page:
            logger.info("Skipping page %d (already checkpointed)", page)
            continue

        listing_url = f"{config.base_url}?page={page}&category={config.category}"
        logger.info("Fetching listing page %d: %s", page, listing_url)

        try:
            listing_resp = await fetch_page(listing_url, config.fetcher_mode, config)
        except Exception as exc:
            logger.error("Failed to fetch listing page %d: %s", page, exc)
            continue

        if not listing_resp.ok:
            logger.error(
                "Listing page %d returned status %d — skipping",
                page, listing_resp.status,
            )
            continue

        article_links = find_article_links_from_listing(listing_resp, config.base_url)
        logger.info("Found %d articles on page %d", len(article_links), page)

        # ── Fetch ALL articles on this page concurrently ──────────────
        # fetch_many's internal Semaphore(concurrency) caps active connections.
        pending_links = [
            info for info in article_links
            if info.get("url") and not state.is_article_processed(str(info["url"]))
        ]

        if not pending_links:
            logger.info("  All articles on page %d already processed", page)
        else:
            fetch_urls: List[str] = [str(info["url"]) for info in pending_links]
            logger.info(
                "  Fetching %d articles concurrently (max %d at once)...",
                len(fetch_urls), config.concurrency,
            )

            responses = await fetch_many(
                fetch_urls,
                mode=config.fetcher_mode,
                config=config,
                concurrency=config.concurrency,
                min_delay=config.min_delay_page,
                max_delay=config.max_delay_page,
            )

            # ── Phase 1: Parse all responses (no network I/O) ────────
            pending_articles: List[Dict[str, Any]] = []

            for resp, link_info in zip(responses, pending_links):
                article_url: str = link_info.get("url") or ""
                card_category = link_info.get("category")

                if not resp.ok:
                    logger.error(
                        "    Failed to fetch article %s (status %d)",
                        article_url, resp.status,
                    )
                    state.add_skipped({
                        "article": article_url, "url": "",
                        "reason": "fetch_error",
                        "detail": f"HTTP {resp.status}",
                        "category": card_category,
                    })
                    state.mark_article_processed(article_url)
                    save_checkpoint(ckpt_path, state)
                    continue

                logger.info("  -> Processing article: %s", article_url)

                matched_keyword: Optional[str] = None
                article_text = ""
                article_title: Optional[str] = None

                if kw_patterns:
                    article_text, article_title = extract_article_text_and_title(resp)
                    fields_to_check: List[str] = []
                    if config.keyword_field in ("body", "both"):
                        fields_to_check.append(article_text)
                    if config.keyword_field in ("title", "both") and article_title:
                        fields_to_check.append(article_title)
                    matched_keyword = match_keywords(kw_patterns, fields_to_check)

                    if not matched_keyword:
                        logger.info("    Skipping article (no keyword match): %s", article_url)
                        state.add_skipped({
                            "article": article_url, "url": "",
                            "reason": "keyword_no_match",
                            "detail": "no matching keyword",
                            "category": card_category,
                        })
                        state.mark_article_processed(article_url)
                        save_checkpoint(ckpt_path, state)
                        continue

                vids = detect_video_urls(resp, debug=config.debug)

                if not vids:
                    logger.info("    No video embeds/links found.")
                    state.add_skipped({
                        "article": article_url, "url": "",
                        "reason": "no_video_found",
                        "detail": "no embeds/links detected",
                        "category": card_category,
                    })
                    state.mark_article_processed(article_url)
                    save_checkpoint(ckpt_path, state)
                    continue

                article_metadata = extract_article_metadata(resp)
                logger.info("    Found %d video(s):", len(vids))
                for v in vids:
                    logger.info("      %s", v)

                pending_articles.append({
                    "url": article_url,
                    "category": card_category,
                    "vids": list(vids),
                    "metadata": article_metadata,
                    "matched_keyword": matched_keyword,
                    "article_text": article_text,
                })

            # ── Phase 2: Probe all new video URLs concurrently ────────
            already_seen = {v.get("url") for v in state.found_videos}
            probe_inputs: List[tuple] = [
                (art, vid_url)
                for art in pending_articles
                for vid_url in art["vids"]
                if vid_url not in already_seen
            ]

            probe_map: Dict[str, Any] = {}
            if probe_inputs:
                logger.info("  Probing %d video(s) concurrently...", len(probe_inputs))
                probe_results = await asyncio.gather(*[
                    _probe_in_executor(
                        vid_url,
                        cookiefile=cookiefile,
                        cookies_from_browser=cookies_browser,
                    )
                    for _, vid_url in probe_inputs
                ])
                probe_map = {
                    vid_url: probe
                    for (_, vid_url), probe in zip(probe_inputs, probe_results)
                }

            # ── Phase 3: Build records and checkpoint per article ─────
            for art in pending_articles:
                article_url = art["url"]
                card_category = art["category"]
                article_metadata = art["metadata"]
                matched_keyword = art["matched_keyword"]
                article_text = art["article_text"]

                for vid_url in art["vids"]:
                    if vid_url in already_seen:
                        logger.debug("      (duplicate, skipping) %s", vid_url)
                        continue

                    probe = probe_map.get(vid_url, {
                        "error": "probe skipped",
                        "has_audio": False,
                        "has_combined": False,
                        "recommended_format": None,
                        "title": None,
                    })
                    chosen = probe.get("recommended_format")
                    video_title = probe.get("title") or ""
                    logger.info(
                        "      probe -> has_audio=%s recommended_format=%s "
                        "title=%s error=%s",
                        probe.get("has_audio"), chosen, video_title, probe.get("error"),
                    )

                    rec: Dict[str, Any] = {
                        "url": vid_url,
                        "chosen_format": chosen,
                        "has_audio": probe.get("has_audio"),
                        "title": video_title,
                        "caption_post": probe.get("caption_post", ""),
                        "article": article_url,
                        "category": card_category,
                        "article_title": article_metadata.get("title"),
                        "date": article_metadata.get("date"),
                        "author": article_metadata.get("author"),
                        "image_url": article_metadata.get("image_url"),
                        "narasi": article_metadata.get("narasi"),
                        "penjelasan": article_metadata.get("penjelasan"),
                        "kesimpulan": article_metadata.get("kesimpulan"),
                        "factcheck_result": article_metadata.get("factcheck_result"),
                        "factcheck_source": article_metadata.get("factcheck_source"),
                        "references": article_metadata.get("references", []),
                    }

                    if probe.get("error"):
                        rec["probe_error"] = probe["error"]
                        state.add_skipped({
                            "article": article_url,
                            "url": vid_url,
                            "reason": "probe_error",
                            "detail": probe["error"],
                            "matched_keyword": matched_keyword or "",
                            "category": card_category,
                        })

                    if matched_keyword:
                        rec["matched_keyword"] = matched_keyword
                        if config.show_snippet and article_text:
                            try:
                                m = re.search(
                                    r"(.{0,40}" + re.escape(matched_keyword) + r".{0,40})",
                                    article_text,
                                    re.IGNORECASE,
                                )
                                rec["snippet"] = m.group(0) if m else ""
                            except Exception:
                                rec["snippet"] = ""

                    state.add_video(rec)
                    already_seen.add(vid_url)

                state.mark_article_processed(article_url)
                save_checkpoint(ckpt_path, state)
        # end else (pending_links)

        # ── Download videos from this page ────────────────────────────
        # Get videos that were found in this page only (not yet downloaded)
        page_videos: List[Dict[str, Any]] = []
        for item in state.found_videos:
            # Skip if already downloaded (has download_attempted flag)
            if item.get("download_attempted"):
                continue
            # Skip if probe error
            if item.get("probe_error"):
                continue
            # Skip if no audio (if configured)
            if config.skip_no_audio and not item.get("has_audio"):
                logger.info("Skipping (no audio): %s", item.get("url"))
                state.add_skipped({
                    "article": item.get("article", ""),
                    "url": item.get("url", ""),
                    "reason": "no_audio",
                    "detail": "probed as no audio",
                    "matched_keyword": item.get("matched_keyword", ""),
                    "category": item.get("category", ""),
                })
                item["download_attempted"] = True
                continue
            page_videos.append(item)

        # Download videos from this page
        if page_videos:
            logger.info("=" * 60)
            logger.info("Downloading %d videos from page %d...", len(page_videos), page)
            logger.info("=" * 60)
            
            page_success = await download_videos_async(
                page_videos,
                download_dir=config.download_dir,
                output_template=config.output_template,
                cookies=config.cookies,
                use_cookies=config.use_cookies,
                min_delay=config.min_delay_dl,
                max_delay=config.max_delay_dl,
                dry_run=config.dry_run,
                cookies_from_browser=config.cookies_from_browser,
                use_cookies_from_browser=config.use_cookies_from_browser,
                smart_cookies=config.smart_cookies,
                concurrency=config.download_concurrency,
            )
            
            # Mark these videos as download attempted
            for item in page_videos:
                item["download_attempted"] = True
            
            logger.info("Page %d download complete: %d/%d succeeded", 
                       page, page_success, len(page_videos))
        else:
            logger.info("No videos to download from page %d", page)

        # Update page progress
        state.last_page = page
        save_checkpoint(ckpt_path, state)

    # ── Post-scrape: export CSVs and final report ─────────────────────
    if not state.found_videos:
        logger.info("No video URLs found across pages.")
        return

    logger.info("Total unique video URLs found: %d", len(state.found_videos))

    # Write CSVs
    os.makedirs(config.download_dir, exist_ok=True)
    write_video_index(config.download_dir, state.found_videos)
    write_extracted_videos(config.download_dir, state.found_videos)
    write_skipped_items(config.download_dir, state.skipped_items)
    write_downloaded_videos(config.download_dir, state.found_videos)

    # Final checkpoint
    save_checkpoint(ckpt_path, state)

    # ── Summary report ────────────────────────────────────────────────
    extracted = [v for v in state.found_videos if not v.get("probe_error")]
    downloaded = [v for v in state.found_videos if v.get("download_attempted") and not v.get("probe_error")]
    logger.info("=" * 60)
    logger.info("SUMMARY")
    logger.info("  Pages scraped       : %d", config.end_page - config.start_page + 1)
    logger.info("  Videos found        : %d", len(state.found_videos))
    logger.info("  Videos extracted    : %d (probe OK)", len(extracted))
    logger.info("  Videos downloaded   : %d", len(downloaded))
    logger.info("  Skipped items       : %d", len(state.skipped_items))
    logger.info("=" * 60)
