#!/usr/bin/env python3
"""DFK Content Downloader — Download videos/content from CSV file with URLs.

Reads "Konten DFK Terverifikasi - Detail data recap.csv" and downloads all
content URLs using yt-dlp. Supports Facebook, Twitter/X, TikTok, Instagram,
YouTube, Threads, and other platforms.

Features:
- Async batch processing with concurrency control
- Checkpoint/resume support
- Per-platform rate limiting
- Automatic yt-dlp installation
- CSV export of download results
- Retry mechanism with exponential backoff
"""
import argparse
import asyncio
import csv
import json
import logging
import os
import random
import re
import subprocess
import sys
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Set
from urllib.parse import urlparse

_SCRAPPER_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _SCRAPPER_DIR not in sys.path:
    sys.path.insert(0, _SCRAPPER_DIR)

from ytdlp_utils import AUTH_ERROR_PATTERNS, is_auth_error  # noqa: E402

# ============================================================================
# Configuration
# ============================================================================

@dataclass
class DownloadConfig:
    """Configuration for DFK content downloader."""
    csv_file: str = "Konten DFK Terverifikasi - Detail data recap.csv"
    download_dir: str = "dfk_downloads"
    output_template: str = "[%(id)s] %(title).100B.%(ext)s"
    
    # Concurrency
    concurrency: int = 3
    
    # Rate limiting (per platform)
    min_delay: float = 2.0
    max_delay: float = 5.0
    
    # Retry
    max_retries: int = 3
    retry_backoff: float = 2.0
    
    # Filters
    start_row: int = 1
    end_row: Optional[int] = None
    platforms: Optional[List[str]] = None  # None = all platforms
    
    # Cookies
    cookies: Optional[str] = None
    cookies_from_browser: Optional[str] = None
    smart_cookies: bool = True  # Try without cookies first, retry with cookies on auth error
    
    # Checkpoint
    checkpoint_file: str = "dfk_checkpoint.json"
    resume: bool = False
    
    # Modes
    dry_run: bool = False
    log_level: str = "INFO"


@dataclass
class CheckpointState:
    """Tracks download progress for resumability."""
    processed_rows: Set[int] = field(default_factory=set)
    downloaded: List[Dict[str, Any]] = field(default_factory=list)
    failed: List[Dict[str, Any]] = field(default_factory=list)
    skipped: List[Dict[str, Any]] = field(default_factory=list)
    last_row: int = 0


# ============================================================================
# Checkpoint I/O
# ============================================================================

def load_checkpoint(path: str) -> CheckpointState:
    """Load checkpoint from JSON file."""
    if not os.path.exists(path):
        return CheckpointState()
    
    try:
        with open(path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        state = CheckpointState(
            processed_rows=set(data.get('processed_rows', [])),
            downloaded=data.get('downloaded', []),
            failed=data.get('failed', []),
            skipped=data.get('skipped', []),
            last_row=data.get('last_row', 0),
        )
        logging.info(
            "Loaded checkpoint: %d processed, %d downloaded, %d failed, %d skipped",
            len(state.processed_rows), len(state.downloaded),
            len(state.failed), len(state.skipped),
        )
        return state
    except Exception as exc:
        logging.error("Failed to load checkpoint: %s", exc)
        return CheckpointState()


def save_checkpoint(path: str, state: CheckpointState) -> None:
    """Save checkpoint to JSON file."""
    try:
        data = {
            'processed_rows': sorted(list(state.processed_rows)),
            'downloaded': state.downloaded,
            'failed': state.failed,
            'skipped': state.skipped,
            'last_row': state.last_row,
        }
        with open(path, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
    except Exception as exc:
        logging.error("Failed to save checkpoint: %s", exc)


# ============================================================================
# CSV Reading
# ============================================================================

def read_csv_rows(
    csv_file: str,
    start_row: int = 1,
    end_row: Optional[int] = None,
    platforms: Optional[List[str]] = None,
) -> List[Dict[str, Any]]:
    """Read CSV and return list of row dicts with URL, platform, category, etc."""
    rows = []
    
    with open(csv_file, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        for idx, row in enumerate(reader, start=1):
            if idx < start_row:
                continue
            if end_row and idx > end_row:
                break
            
            url = row.get('URL KONTEN', '').strip()
            if not url:
                continue
            
            platform = normalize_platform(row.get('PLATFORM', '').strip())
            if platforms and platform not in platforms:
                continue
            
            rows.append({
                'row_num': idx,
                'url': url,
                'platform': platform,
                'category': row.get('KATEGORI', '').strip(),
                'date': row.get('Tanggal', '').strip(),
                'description': row.get('ANALISIS PELANGGARAN', '').strip()[:200],
            })
    
    return rows


def normalize_platform(platform: str) -> str:
    """Normalize platform names (TikTok/Tiktok/TIkTok -> tiktok)."""
    platform_lower = platform.lower()
    
    if 'tiktok' in platform_lower or 'tik tok' in platform_lower:
        return 'tiktok'
    if 'facebook' in platform_lower or 'fb' in platform_lower:
        return 'facebook'
    if 'twitter' in platform_lower or platform_lower == 'x':
        return 'twitter'
    if 'instagram' in platform_lower or 'ig' in platform_lower:
        return 'instagram'
    if 'youtube' in platform_lower or 'yt' in platform_lower:
        return 'youtube'
    if 'threads' in platform_lower:
        return 'threads'
    
    return platform_lower if platform_lower else 'unknown'


# ============================================================================
# yt-dlp wrapper
# ============================================================================

def ensure_yt_dlp() -> None:
    """Ensure yt-dlp is installed."""
    try:
        subprocess.run(
            [sys.executable, '-m', 'yt_dlp', '--version'],
            check=True,
            capture_output=True,
        )
    except subprocess.CalledProcessError:
        logging.info("yt-dlp not found, installing...")
        subprocess.run([sys.executable, '-m', 'pip', 'install', 'yt-dlp'], check=True)


async def fetch_caption(url: str, timeout_sec: int = 30) -> tuple:
    """Fetch post caption/description using yt-dlp --print description/title.

    Returns (caption_text, source, status) where source is 'description'|'title'
    and status is 'ok'|'empty'|'failed'|'timeout'|'error:...'
    """
    cmd = [
        sys.executable, '-m', 'yt_dlp',
        '--skip-download', '--no-warnings', '--quiet',
        '--socket-timeout', '10',
        '--print', 'description',
        '--print', 'title',
        url,
    ]
    loop = asyncio.get_running_loop()
    try:
        proc = await loop.run_in_executor(
            None,
            lambda: subprocess.run(
                cmd, capture_output=True, text=True,
                encoding='utf-8', errors='replace',
                timeout=timeout_sec,
            ),
        )
    except subprocess.TimeoutExpired:
        return '', '', 'timeout'
    except Exception as exc:
        return '', '', f'error:{type(exc).__name__}'

    if proc.returncode != 0:
        return '', '', 'failed'

    def _clean(s: str) -> str:
        return ' '.join(s.replace('\r', ' ').split()).strip()

    lines = [_clean(x) for x in proc.stdout.splitlines()]
    nonempty = [x for x in lines if x]
    if not nonempty:
        return '', '', 'empty'

    # yt-dlp prints description first, then title (matching --print order)
    if lines and lines[0]:
        return lines[0], 'description', 'ok'
    return nonempty[0], 'title', 'ok'


async def _run_ytdlp(
    url: str,
    download_dir: str,
    output_template: str,
    cookies: Optional[str] = None,
    cookies_from_browser: Optional[str] = None,
    max_retries: int = 3,
    retry_backoff: float = 2.0,
) -> Dict[str, Any]:
    """Low-level yt-dlp subprocess call with retry loop.

    Returns dict with keys: success, url, error, output_path, attempt.
    """
    cmd = [sys.executable, '-m', 'yt_dlp', url, '--no-playlist']

    # Restrict filenames (sanitize for Windows)
    cmd.append('--restrict-filenames')

    # Output template
    out = os.path.join(download_dir, output_template)
    cmd.extend(['-o', out])

    # Cookies
    if cookies:
        cmd.extend(['--cookies', cookies])
    if cookies_from_browser:
        cmd.extend(['--cookies-from-browser', cookies_from_browser])

    # Retries (yt-dlp internal network retries)
    cmd.extend(['--retries', str(max_retries)])

    # Print final filepath after download
    cmd.extend(['--print', 'after_move:filepath'])

    for attempt in range(1, max_retries + 1):
        try:
            loop = asyncio.get_running_loop()
            # Capture cmd in default arg to avoid late-binding closure issue
            proc = await loop.run_in_executor(
                None,
                lambda _cmd=cmd: subprocess.run(
                    _cmd,
                    capture_output=True,
                    text=True,
                    timeout=300,  # 5 min timeout per download
                )
            )

            if proc.returncode == 0:
                output = proc.stdout.strip().split('\n')[-1] if proc.stdout else None
                return {
                    'success': True,
                    'url': url,
                    'output_path': output,
                    'attempt': attempt,
                }
            else:
                error = proc.stderr.strip() if proc.stderr else f"Exit code {proc.returncode}"

                if attempt < max_retries:
                    wait = retry_backoff ** (attempt - 1)
                    logging.warning(
                        "Download failed (attempt %d/%d): %s — retrying in %.1fs",
                        attempt, max_retries, error, wait,
                    )
                    await asyncio.sleep(wait)
                else:
                    return {
                        'success': False,
                        'url': url,
                        'error': error,
                        'attempts': max_retries,
                    }

        except subprocess.TimeoutExpired:
            if attempt < max_retries:
                logging.warning("Download timeout (attempt %d/%d), retrying...", attempt, max_retries)
                await asyncio.sleep(retry_backoff ** (attempt - 1))
            else:
                return {
                    'success': False,
                    'url': url,
                    'error': 'Download timeout after retries',
                    'attempts': max_retries,
                }

        except Exception as exc:
            logging.error("Download exception: %s", exc)
            return {
                'success': False,
                'url': url,
                'error': str(exc),
                'attempts': attempt,
            }

    return {'success': False, 'url': url, 'error': 'Unknown error'}


async def download_url(
    url: str,
    download_dir: str,
    output_template: str,
    cookies: Optional[str] = None,
    cookies_from_browser: Optional[str] = None,
    smart_cookies: bool = True,
    max_retries: int = 3,
    retry_backoff: float = 2.0,
    dry_run: bool = False,
) -> Dict[str, Any]:
    """Download a single URL with yt-dlp.

    When *smart_cookies* is True and cookies are configured, the function
    first attempts the download **without** cookies.  If that attempt fails
    with an authentication-related error it automatically retries **with**
    cookies.  This avoids burning cookie sessions on content that is
    publicly accessible.
    """
    if dry_run:
        logging.info("[DRY-RUN] Would download: %s", url)
        return {
            'success': True,
            'url': url,
            'dry_run': True,
            'output_path': None,
        }

    has_cookies = bool(cookies or cookies_from_browser)

    # ------------------------------------------------------------------
    # Smart-cookie path: try without cookies first
    # ------------------------------------------------------------------
    if smart_cookies and has_cookies:
        logging.debug("Smart-cookies: trying without auth first — %s", url[:80])
        result = await _run_ytdlp(
            url, download_dir, output_template,
            cookies=None, cookies_from_browser=None,
            max_retries=1,        # single quick attempt
            retry_backoff=retry_backoff,
        )

        if result.get('success'):
            result['auth_used'] = False
            return result

        # Check whether the error looks like an auth / login issue
        error_msg = result.get('error', '')
        if is_auth_error(error_msg):
            logging.info("Auth error detected, retrying WITH cookies — %s", url[:80])
            result = await _run_ytdlp(
                url, download_dir, output_template,
                cookies=cookies,
                cookies_from_browser=cookies_from_browser,
                max_retries=max_retries,
                retry_backoff=retry_backoff,
            )
            result['auth_used'] = True
            return result

        # Non-auth error (e.g. "no video in post", network error, etc.)
        # No point retrying with cookies — return as-is.
        result['auth_used'] = False
        return result

    # ------------------------------------------------------------------
    # Normal path: always use cookies if provided (smart_cookies=False)
    # ------------------------------------------------------------------
    result = await _run_ytdlp(
        url, download_dir, output_template,
        cookies=cookies,
        cookies_from_browser=cookies_from_browser,
        max_retries=max_retries,
        retry_backoff=retry_backoff,
    )
    result['auth_used'] = has_cookies
    return result


# ============================================================================
# Batch downloader
# ============================================================================

async def download_batch(
    rows: List[Dict[str, Any]],
    config: DownloadConfig,
    state: CheckpointState,
) -> None:
    """Download a batch of rows concurrently with rate limiting."""
    sem = asyncio.Semaphore(config.concurrency)
    
    async def _download_row(row: Dict[str, Any]) -> None:
        async with sem:
            row_num = row['row_num']
            
            # Skip if already processed
            if row_num in state.processed_rows:
                logging.debug("Skipping row %d (already processed)", row_num)
                return
            
            url = row['url']
            platform = row['platform']
            
            logging.info("[%d/%d] Downloading (%s): %s", row_num, len(rows), platform, url[:80])
            
            # Fetch caption and download concurrently
            caption_task = asyncio.create_task(fetch_caption(url, timeout_sec=30))
            dl_task = asyncio.create_task(download_url(
                url,
                download_dir=config.download_dir,
                output_template=config.output_template,
                cookies=config.cookies,
                cookies_from_browser=config.cookies_from_browser,
                smart_cookies=config.smart_cookies,
                max_retries=config.max_retries,
                retry_backoff=config.retry_backoff,
                dry_run=config.dry_run,
            ))
            result, (caption, caption_source, caption_status) = await asyncio.gather(
                dl_task, caption_task
            )

            # Merge row metadata with result
            result.update({
                'row_num': row_num,
                'platform': platform,
                'category': row.get('category'),
                'date': row.get('date'),
                'caption_post': caption,
                'caption_source': caption_source,
                'caption_status': caption_status,
            })

            if result.get('success'):
                state.downloaded.append(result)
                auth_tag = " (with cookies)" if result.get('auth_used') else " (no cookies)"
                logging.info("  ✓ Downloaded%s [caption=%s]: %s",
                             auth_tag, caption_status, result.get('output_path', 'dry-run'))
            else:
                state.failed.append(result)
                logging.error("  ✗ Failed: %s", result.get('error'))
            
            state.processed_rows.add(row_num)
            state.last_row = max(state.last_row, row_num)
            
            # Save checkpoint after each download
            save_checkpoint(config.checkpoint_file, state)
            
            # Rate limiting
            delay = random.uniform(config.min_delay, config.max_delay)
            await asyncio.sleep(delay)
    
    tasks = [asyncio.create_task(_download_row(row)) for row in rows]
    await asyncio.gather(*tasks)


# ============================================================================
# CSV Export
# ============================================================================

def export_results(download_dir: str, state: CheckpointState) -> None:
    """Export download results to CSV files."""
    os.makedirs(download_dir, exist_ok=True)
    
    # Downloaded
    if state.downloaded:
        csv_path = os.path.join(download_dir, 'dfk_downloaded.csv')
        with open(csv_path, 'w', encoding='utf-8', newline='') as f:
            writer = csv.DictWriter(f, fieldnames=[
                'row_num', 'url', 'platform', 'category', 'date',
                'caption_post', 'caption_source', 'caption_status',
                'output_path', 'attempt', 'auth_used',
            ])
            writer.writeheader()
            for item in state.downloaded:
                writer.writerow({
                    'row_num': item.get('row_num'),
                    'url': item.get('url'),
                    'platform': item.get('platform'),
                    'category': item.get('category'),
                    'date': item.get('date'),
                    'caption_post': item.get('caption_post', ''),
                    'caption_source': item.get('caption_source', ''),
                    'caption_status': item.get('caption_status', ''),
                    'output_path': item.get('output_path'),
                    'attempt': item.get('attempt'),
                    'auth_used': item.get('auth_used', ''),
                })
        logging.info("Exported %d downloads to %s", len(state.downloaded), csv_path)
    
    # Failed
    if state.failed:
        csv_path = os.path.join(download_dir, 'dfk_failed.csv')
        with open(csv_path, 'w', encoding='utf-8', newline='') as f:
            writer = csv.DictWriter(f, fieldnames=[
                'row_num', 'url', 'platform', 'category', 'date',
                'error', 'attempts',
            ])
            writer.writeheader()
            for item in state.failed:
                writer.writerow({
                    'row_num': item.get('row_num'),
                    'url': item.get('url'),
                    'platform': item.get('platform'),
                    'category': item.get('category'),
                    'date': item.get('date'),
                    'error': item.get('error'),
                    'attempts': item.get('attempts'),
                })
        logging.info("Exported %d failures to %s", len(state.failed), csv_path)


# ============================================================================
# Main
# ============================================================================

async def main_async(config: DownloadConfig) -> None:
    """Async main entry point."""
    # Ensure yt-dlp is installed
    ensure_yt_dlp()
    
    # Create download dir
    os.makedirs(config.download_dir, exist_ok=True)
    
    # Load checkpoint
    state = CheckpointState()
    if config.resume:
        state = load_checkpoint(config.checkpoint_file)
        logging.info("Resuming from checkpoint")
    
    # Read CSV
    logging.info("Reading CSV: %s", config.csv_file)
    rows = read_csv_rows(
        config.csv_file,
        start_row=config.start_row,
        end_row=config.end_row,
        platforms=config.platforms,
    )
    logging.info("Found %d URLs to download", len(rows))
    
    if not rows:
        logging.warning("No URLs found matching criteria")
        return
    
    # Filter already-processed rows
    if config.resume:
        rows = [r for r in rows if r['row_num'] not in state.processed_rows]
        logging.info("After filtering processed: %d URLs remaining", len(rows))
    
    if not rows:
        logging.info("All URLs already processed")
        export_results(config.download_dir, state)
        return
    
    # Download batch
    await download_batch(rows, config, state)
    
    # Export results
    export_results(config.download_dir, state)
    
    # Summary
    logging.info("=" * 60)
    logging.info("SUMMARY")
    logging.info("  Total processed : %d", len(state.processed_rows))
    logging.info("  Downloaded      : %d", len(state.downloaded))
    logging.info("  Failed          : %d", len(state.failed))
    logging.info("=" * 60)


def main() -> None:
    """CLI entry point."""
    parser = argparse.ArgumentParser(
        description="Download DFK content URLs from CSV using yt-dlp"
    )
    
    # Input
    parser.add_argument('--csv-file', default='Konten DFK Terverifikasi - Detail data recap.csv',
                        help='Path to CSV file with URLs')
    parser.add_argument('--start-row', type=int, default=1,
                        help='First row to process (1-indexed)')
    parser.add_argument('--end-row', type=int,
                        help='Last row to process (inclusive)')
    parser.add_argument('--platforms', nargs='+',
                        help='Filter by platforms (e.g. tiktok facebook twitter)')
    
    # Output
    parser.add_argument('--download-dir', default='dfk_downloads',
                        help='Output directory for downloads')
    parser.add_argument('--output', default='[%(id)s] %(title).100B.%(ext)s',
                        help='yt-dlp output template (sanitized for Windows)')
    
    # Concurrency
    parser.add_argument('--concurrency', type=int, default=3,
                        help='Max concurrent downloads')
    parser.add_argument('--min-delay', type=float, default=2.0,
                        help='Min delay between downloads')
    parser.add_argument('--max-delay', type=float, default=5.0,
                        help='Max delay between downloads')
    
    # Retry
    parser.add_argument('--max-retries', type=int, default=3,
                        help='Max retries per download')
    parser.add_argument('--retry-backoff', type=float, default=2.0,
                        help='Exponential backoff base for retries')
    
    # Cookies
    parser.add_argument('--cookies',
                        help='Netscape-format cookies file')
    parser.add_argument('--cookies-from-browser',
                        help='Import cookies from browser (e.g. chrome, firefox)')
    parser.add_argument('--no-smart-cookies', action='store_true',
                        help='Disable smart cookies (always send cookies on every request)')
    
    # Checkpoint
    parser.add_argument('--checkpoint-file', default='dfk_checkpoint.json',
                        help='Checkpoint file path')
    parser.add_argument('--resume', action='store_true',
                        help='Resume from checkpoint')
    
    # Modes
    parser.add_argument('--dry-run', action='store_true',
                        help='Simulate downloads without actually downloading')
    parser.add_argument('--log-level', default='INFO',
                        choices=['DEBUG', 'INFO', 'WARNING', 'ERROR'],
                        help='Logging verbosity')
    
    args = parser.parse_args()
    
    # Setup logging
    logging.basicConfig(
        level=getattr(logging, args.log_level),
        format='%(asctime)s [%(levelname)s] %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S',
    )
    
    # Build config
    config = DownloadConfig(
        csv_file=args.csv_file,
        download_dir=args.download_dir,
        output_template=args.output,
        concurrency=args.concurrency,
        min_delay=args.min_delay,
        max_delay=args.max_delay,
        max_retries=args.max_retries,
        retry_backoff=args.retry_backoff,
        start_row=args.start_row,
        end_row=args.end_row,
        platforms=args.platforms,
        cookies=args.cookies,
        cookies_from_browser=args.cookies_from_browser,
        smart_cookies=not args.no_smart_cookies,
        checkpoint_file=args.checkpoint_file,
        resume=args.resume,
        dry_run=args.dry_run,
        log_level=args.log_level,
    )
    
    # Run
    asyncio.run(main_async(config))


if __name__ == '__main__':
    main()
