AITF — Video Scraper & Downloader
=================================

This workspace contains tools to find and download embedded videos from article listing pages (default: TurnBackHoax), CSV files with URLs, and single URLs.

## Tools

### 1. `scrape_and_download_videos.py` — TurnBackHoax scraper
Modular async scraper for TurnBackHoax article pages with Scrapling-based fetching.

### 2. `dfk_downloader.py` — CSV batch downloader ⭐ NEW
Async batch downloader that reads URLs from CSV files (4,000+ URLs supported).

### 3. `download_single_video.py` — Single URL downloader
Simple wrapper around yt-dlp for one-off downloads.

## Architecture

The main scraper has been refactored from a single 655-line script into a modular async package:

```
scrapper/
├── turnbackhoax/          # Main package
│   ├── __init__.py        # Vendored Scrapling sys.path setup
│   ├── config.py          # ScrapeConfig dataclass + CLI arg parser
│   ├── checkpoint.py      # JSON checkpoint for resumable scraping
│   ├── fetcher.py         # Async fetching (http/dynamic/stealth modes)
│   ├── parser.py          # HTML parsing — article links, video detection, keywords
│   ├── prober.py          # yt-dlp video probing (format detection, audio check)
│   ├── downloader.py      # yt-dlp video downloading
│   ├── exporter.py        # CSV export (video_index, extracted_videos, skipped_items)
│   ├── runner.py          # Async orchestrator — main pipeline
│   └── cli.py             # Entry point (wraps asyncio.run)
├── scrape_and_download_videos.py   # Thin wrapper → turnbackhoax.cli.main()
├── dfk_downloader.py               # CSV batch downloader ⭐ NEW
├── download_single_video.py        # Standalone single-URL downloader
├── Scrapling/             # Vendored Scrapling v0.4.1 (used instead of requests+BS4)
├── instaloader/           # Vendored Instaloader v4.15 (reference, not integrated)
└── scrapy/                # Vendored Scrapy (reference, not integrated)
```

## Key features

- **Scrapling-based fetching** — replaces `requests` + `BeautifulSoup` with Scrapling's CSS/XPath selectors
- **Three fetcher modes**: `http` (fast, curl_cffi), `dynamic` (Playwright JS rendering), `stealth` (anti-bot/Cloudflare bypass)
- **Async concurrency** — `asyncio.Semaphore`-based throttling for parallel article fetches
- **Resumable** — JSON checkpoint files track progress; `--resume` picks up where you left off
- **Keyword filtering** — whole-word or substring matching on article body/title
- **Video probing** — yt-dlp detects formats, audio presence, and recommends best format
- **Dry-run mode** — `--dry-run` does everything except actual downloads

## Quick requirements

- Python 3.10+
- `yt-dlp` (auto-installed when needed)
- `ffmpeg` on PATH (recommended for best video+audio merging)

## Install dependencies

```sh
pip install -r requirements.txt
```

For browser-based fetching (`--fetcher-mode dynamic` or `stealth`):
```sh
pip install playwright && python -m playwright install chromium
```

## Usage — scrape_and_download_videos.py

```sh
# Scrape page 1 only (default: politik category)
python scrapper/scrape_and_download_videos.py --start-page 1 --end-page 1

# Scrape pages 1..5, save to custom folder, with 3 concurrent fetches
python scrapper/scrape_and_download_videos.py --start-page 1 --end-page 5 --download-dir videos --concurrency 3

# Dry run — probe videos but don't download
python scrapper/scrape_and_download_videos.py --start-page 1 --end-page 3 --dry-run

# Resume from checkpoint
python scrapper/scrape_and_download_videos.py --start-page 1 --end-page 10 --resume

# Filter articles by keyword
python scrapper/scrape_and_download_videos.py --start-page 1 --end-page 5 \
    --keyword "vaksin" --keyword "hoax" --keyword-mode whole --keyword-field both

# Use stealth mode for anti-bot sites (requires playwright + chromium)
python scrapper/scrape_and_download_videos.py --start-page 1 --end-page 1 \
    --fetcher-mode stealth

# With cookies for authenticated downloads
python scrapper/scrape_and_download_videos.py --start-page 1 --end-page 2 \
    --cookies cookies.txt --confirm-cookies

# Pass cookies from browser
python scrapper/scrape_and_download_videos.py --start-page 1 --end-page 2 \
    --cookies-from-browser chrome
```

## CLI flags

| Flag | Default | Description |
|------|---------|-------------|
| `--start-page` | 1 | First listing page to scrape |
| `--end-page` | 1 | Last listing page to scrape |
| `--category` | politik | Category filter for listing URL |
| `--base-url` | `https://turnbackhoax.id/articles` | Base listing URL |
| `--download-dir` | `downloaded_videos` | Output directory |
| `--output` | yt-dlp default | yt-dlp output template |
| `--cookies` | — | Netscape-format cookies file |
| `--confirm-cookies` | false | Must be set to actually use `--cookies` |
| `--cookies-from-browser` | — | Import cookies from browser (e.g. `chrome`) |
| `--fetcher-mode` | `http` | `http`, `dynamic`, or `stealth` |
| `--concurrency` | 5 | Max concurrent article fetches |
| `--user-agent` | default | Custom User-Agent string |
| `--checkpoint-file` | `<download-dir>/checkpoint.json` | Checkpoint file path |
| `--resume` | false | Resume from last checkpoint |
| `--keyword` | — | Filter keyword (repeatable) |
| `--keyword-mode` | `whole` | `whole` or `substring` |
| `--keyword-field` | `both` | `body`, `title`, or `both` |
| `--show-snippet` | false | Include keyword context in CSV |
| `--skip-no-audio` | false | Skip videos without audio |
| `--dry-run` | false | Probe but don't download |
| `--debug` | false | Verbose URL filtering logs |
| `--log-level` | `INFO` | `DEBUG`, `INFO`, `WARNING`, `ERROR` |
| `--min-delay-page` | 2.0 | Min delay between article fetches |
| `--max-delay-page` | 4.0 | Max delay between article fetches |
| `--min-delay-dl` | 5.0 | Min delay between downloads |
| `--max-delay-dl` | 10.0 | Max delay between downloads |

## Usage — dfk_downloader.py (CSV batch downloader)

```sh
# Download first 10 URLs from CSV (default: Konten DFK Terverifikasi - Detail data recap.csv)
python scrapper/dfk_downloader.py --max-urls 10

# Download all Facebook and Twitter videos with 10 concurrent downloads
python scrapper/dfk_downloader.py --platforms facebook twitter --concurrency 10

# Dry run — check what would be downloaded without actually downloading
python scrapper/dfk_downloader.py --max-urls 50 --dry-run

# Resume from previous checkpoint
python scrapper/dfk_downloader.py --resume

# Custom CSV file and output directory
python scrapper/dfk_downloader.py --csv-path "my_urls.csv" --output-dir "my_downloads"

# Skip already downloaded videos (based on video ID)
python scrapper/dfk_downloader.py --skip-existing

# With custom checkpoint file and retry settings
python scrapper/dfk_downloader.py --checkpoint-file "my_checkpoint.json" --max-retries 5

# Download only TikTok videos with verbose logging
python scrapper/dfk_downloader.py --platforms tiktok --log-level DEBUG
```

### CSV format requirements

The CSV must contain at least a `URL KONTEN` column (or customize with `--url-column`). Optional `PLATFORM` column for filtering. Example:

```csv
No,Tanggal,URL KONTEN,PLATFORM,KATEGORI
1,2024-01-15,https://www.facebook.com/watch?v=12345,Facebook,Hoax
2,2024-01-16,https://twitter.com/user/status/67890,Twitter,Disinformasi
```

### CLI flags — dfk_downloader.py

| Flag | Default | Description |
|------|---------|-------------|
| `--csv-path` | `Konten DFK Terverifikasi - Detail data recap.csv` | Path to CSV file with URLs |
| `--output-dir` | `dfk_downloads` | Output directory for downloads |
| `--url-column` | `URL KONTEN` | CSV column name containing URLs |
| `--platform-column` | `PLATFORM` | CSV column name for platform filtering |
| `--platforms` | all | Filter specific platforms (e.g., `facebook twitter`) |
| `--max-urls` | unlimited | Limit number of URLs to process |
| `--concurrency` | 5 | Max concurrent downloads |
| `--checkpoint-file` | `<output-dir>/dfk_checkpoint.json` | Checkpoint file path |
| `--resume` | false | Resume from checkpoint |
| `--skip-existing` | false | Skip URLs already in checkpoint |
| `--max-retries` | 3 | Max retry attempts per URL |
| `--dry-run` | false | Check URLs without downloading |
| `--log-level` | `INFO` | `DEBUG`, `INFO`, `WARNING`, `ERROR` |
| `--cookies` | — | Netscape-format cookies file |
| `--cookies-from-browser` | — | Import cookies from browser (e.g., `chrome`) |

### Output files — dfk_downloader.py

After running, `<output-dir>/` contains:
- `dfk_checkpoint.json` — resumable state with all processed URLs
- `dfk_results.csv` — summary of all downloads (status, filename, error messages)
- `dfk_downloaded.csv` — successfully downloaded videos only
- `dfk_failed.csv` — failed downloads with error details
- Downloaded video files with sanitized filenames: `[video_id] title.ext`

### Platform support

Tested platforms: **Facebook**, **Twitter/X**, **TikTok**, **Instagram**, **YouTube**, **Threads**

Note: Some platforms may block downloads based on IP location, account requirements, or deleted content. Use `--cookies` or `--cookies-from-browser` for authenticated access.

## Usage — download_single_video.py

```sh
# Download a single public video
python scrapper/download_single_video.py "https://www.facebook.com/.../videos/12345/"

# Specify output template
python scrapper/download_single_video.py <URL> --output "C:/Videos/%(title)s.%(ext)s"

# Use cookies for private videos
python scrapper/download_single_video.py <URL> --cookies cookies.txt
```

## How it works

### scrape_and_download_videos.py pipeline

1. **Listing pages** are fetched using Scrapling's `AsyncFetcher` (or browser-based fetchers)
2. **Article cards** are identified by `.news-card-h-alt` CSS class; links resolved relative to base URL
3. **Articles** are fetched concurrently in batches (controlled by `--concurrency`)
4. **Keyword filtering** (optional) — articles not matching any keyword are skipped
5. **Video detection** — each article is scanned for video URLs in iframes, anchors, and plaintext
6. **Probing** — `yt-dlp --skip-download --dump-json` detects formats and audio presence
7. **Checkpointing** — progress saved to JSON after every article
8. **CSV export** — `video_index.csv`, `extracted_videos.csv`, `skipped_items.csv`
9. **Downloading** — yt-dlp downloads with randomized delays between items

### dfk_downloader.py pipeline

1. **CSV parsing** — reads URLs from specified column, normalizes platform names
2. **Platform filtering** — optionally processes only specific platforms (Facebook, Twitter, etc.)
3. **Checkpoint loading** — skips already-processed URLs if `--resume` or `--skip-existing` is set
4. **Async batch processing** — downloads URLs concurrently with semaphore-based throttling
5. **Retry logic** — exponential backoff for transient failures (network errors, rate limits)
6. **Filename sanitization** — template `[%(id)s] %(title).100B.%(ext)s` with `--restrict-filenames` for Windows compatibility
7. **Result tracking** — all URLs categorized as downloaded, failed (with error), or skipped
8. **CSV export** — three result files (all, downloaded only, failed only) for easy analysis

## Output files

After a run, `<download-dir>/` contains:
- `checkpoint.json` — resumable state
- `video_index.csv` — all detected videos (including probe failures)
- `extracted_videos.csv` — successfully probed videos
- `skipped_items.csv` — articles/videos that were skipped (with reasons)
- Downloaded video files

## Safety & etiquette

- Randomized delays between requests and downloads reduce load on target sites
- Do not pass personal account cookies unless necessary; use `--confirm-cookies` as a safety gate
- Respect site Terms of Service, copyright, and applicable laws

## Installing ffmpeg

**Windows**: Download from [gyan.dev](https://www.gyan.dev/ffmpeg/builds/) or [ffmpeg.org](https://ffmpeg.org/download.html), extract, and add the `bin` folder to your PATH.

**macOS**: `brew install ffmpeg`

**Linux**: `sudo apt install ffmpeg` (or equivalent for your distro)

Without ffmpeg, yt-dlp falls back to single-file formats (lower quality).
