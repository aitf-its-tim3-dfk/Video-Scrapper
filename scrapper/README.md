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
- **Smart cookies** — tries without cookies first; retries with cookies only on auth errors (preserves cookie sessions)
- **Format fallback** — auto-retries without format selector when specific formats aren't available (fixes YouTube Shorts)
- **Windows-compatible filenames** — sanitized filenames with length limits (100 chars) for cross-platform compatibility
- **Rich metadata extraction** — extracts date, author, narasi, penjelasan, kesimpulan, factcheck results, and references from each article
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

# With cookies for authenticated downloads (smart cookies enabled by default)
python scrapper/scrape_and_download_videos.py --start-page 1 --end-page 2 \
    --cookies cookies.txt --confirm-cookies

# Pass cookies from browser (always fresh cookies from logged-in browser)
python scrapper/scrape_and_download_videos.py --start-page 1 --end-page 2 \
    --cookies-from-browser chrome

# Disable smart cookies — always send cookies on every request
python scrapper/scrape_and_download_videos.py --start-page 1 --end-page 2 \
    --cookies cookies.txt --confirm-cookies --no-smart-cookies
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
| `--no-smart-cookies` | false | Disable smart cookies (always send cookies on every request) |
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

### Smart cookies — scrape_and_download_videos.py

By default, `--cookies` and `--cookies-from-browser` use **smart cookie mode**:

1. First attempt downloads **without** cookies (fast, no auth overhead)
2. If yt-dlp returns an authentication error (login required, HTTP 400/401/403, rate-limit, etc.) the download is retried **with** cookies
3. If the error is non-auth (e.g. "no video in this post", network timeout) cookies are not wasted

This preserves cookie sessions for platforms that actually need them (Instagram, private Facebook) while keeping public content downloads (TikTok, YouTube) lightweight.

Disable with `--no-smart-cookies` to always send cookies on every request.

## Usage — dfk_downloader.py (CSV batch downloader)

```sh
# Download first 10 rows from CSV
python scrapper/dfk_downloader.py --end-row 10

# Download all Facebook and Twitter videos
python scrapper/dfk_downloader.py --platforms facebook twitter

# Dry run — check what would be downloaded without actually downloading
python scrapper/dfk_downloader.py --end-row 50 --dry-run

# Resume from previous checkpoint
python scrapper/dfk_downloader.py --resume

# With cookies (smart cookies enabled by default — tries without cookies first,
# retries with cookies only on auth errors like Instagram login-required)
python scrapper/dfk_downloader.py --cookies cookies.txt --resume

# With browser cookie extraction (always fresh cookies from logged-in browser)
python scrapper/dfk_downloader.py --cookies-from-browser chrome --resume

# Disable smart cookies — always send cookies on every request
python scrapper/dfk_downloader.py --cookies cookies.txt --no-smart-cookies --resume

# Download only Instagram with longer delays to avoid rate limits
python scrapper/dfk_downloader.py --platforms instagram --cookies cookies.txt \
    --min-delay 3.0 --max-delay 8.0 --concurrency 2 --resume

# Custom CSV file and output directory
python scrapper/dfk_downloader.py --csv-file "my_urls.csv" --download-dir "my_downloads"

# Download rows 100..200 with verbose logging
python scrapper/dfk_downloader.py --start-row 100 --end-row 200 --log-level DEBUG
```

### Smart cookies

By default, `--cookies` and `--cookies-from-browser` use **smart cookie mode**:

1. First attempt downloads **without** cookies (fast, no auth overhead)
2. If yt-dlp returns an authentication error (login required, HTTP 400/401/403, rate-limit, etc.) the download is retried **with** cookies
3. If the error is non-auth (e.g. "no video in this post", network timeout) cookies are not wasted

This preserves cookie sessions for platforms that actually need them (Instagram, private Facebook) while keeping public content downloads (TikTok, YouTube) lightweight.

Disable with `--no-smart-cookies` to always send cookies on every request.

### CSV format requirements

The CSV must contain a `URL KONTEN` column. Optional `PLATFORM` column for filtering. Example:

```csv
No,Tanggal,URL KONTEN,PLATFORM,KATEGORI
1,2024-01-15,https://www.facebook.com/watch?v=12345,Facebook,Hoax
2,2024-01-16,https://twitter.com/user/status/67890,Twitter,Disinformasi
```

### CLI flags — dfk_downloader.py

| Flag | Default | Description |
|------|---------|-------------|
| `--csv-file` | `Konten DFK Terverifikasi - Detail data recap.csv` | Path to CSV file with URLs |
| `--download-dir` | `dfk_downloads` | Output directory for downloads |
| `--output` | `[%(id)s] %(title).100B.%(ext)s` | yt-dlp output template (sanitized for Windows) |
| `--start-row` | 1 | First row to process (1-indexed) |
| `--end-row` | unlimited | Last row to process (inclusive) |
| `--platforms` | all | Filter specific platforms (e.g., `facebook twitter instagram`) |
| `--concurrency` | 3 | Max concurrent downloads |
| `--min-delay` | 2.0 | Min delay between downloads (seconds) |
| `--max-delay` | 5.0 | Max delay between downloads (seconds) |
| `--max-retries` | 3 | Max retry attempts per URL |
| `--retry-backoff` | 2.0 | Exponential backoff base for retries |
| `--cookies` | — | Netscape-format cookies file |
| `--cookies-from-browser` | — | Import cookies from browser (e.g., `chrome`, `firefox`) |
| `--no-smart-cookies` | false | Disable smart cookies (always send cookies on every request) |
| `--checkpoint-file` | `dfk_checkpoint.json` | Checkpoint file path |
| `--resume` | false | Resume from checkpoint |
| `--dry-run` | false | Check URLs without downloading |
| `--log-level` | `INFO` | `DEBUG`, `INFO`, `WARNING`, `ERROR` |

### Output files — dfk_downloader.py

After running, `<download-dir>/` contains:
- `dfk_downloaded.csv` — successfully downloaded videos (includes `auth_used` column showing whether cookies were needed)
- `dfk_failed.csv` — failed downloads with error details
- Downloaded media files with sanitized filenames: `[video_id] title.ext`

Checkpoint file (default `dfk_checkpoint.json` in working directory) tracks all progress for resumability.

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
5. **Video detection** — each article is scanned for video URLs (Facebook `/share/r/`, `/reel`, Instagram, TikTok, YouTube, etc.)
6. **Probing** — `yt-dlp --skip-download --dump-json` detects formats and audio presence
7. **Checkpointing** — progress saved to JSON after every article
8. **CSV export** — `video_index.csv`, `extracted_videos.csv`, `skipped_items.csv`
9. **Downloading** — yt-dlp downloads with:
   - **Smart cookies** — tries without cookies first; retries with cookies only on auth errors
   - **Format fallback** — retries without format selector if requested format unavailable (fixes YouTube Shorts)
   - **Filename sanitization** — `--restrict-filenames` + 100-char title limit for Windows compatibility
   - Randomized delays between downloads

### dfk_downloader.py pipeline

1. **CSV parsing** — reads URLs from `URL KONTEN` column, normalizes platform names
2. **Platform filtering** — optionally processes only specific platforms (Facebook, Twitter, etc.)
3. **Checkpoint loading** — skips already-processed rows if `--resume` is set
4. **Async batch processing** — downloads URLs concurrently with semaphore-based throttling
5. **Smart cookies** — tries without cookies first; retries with cookies only on auth errors (configurable via `--no-smart-cookies`)
6. **Retry logic** — exponential backoff for transient failures (network errors, rate limits)
7. **Filename sanitization** — template `[%(id)s] %(title).100B.%(ext)s` with `--restrict-filenames` for Windows compatibility
8. **Result tracking** — all URLs categorized as downloaded or failed, with `auth_used` metadata
9. **CSV export** — two result files (downloaded, failed) for easy analysis

## Output files

After a run, `<download-dir>/` contains:
- `checkpoint.json` — resumable state
- `video_index.csv` — all detected videos (including probe failures) **with full metadata**
- `extracted_videos.csv` — successfully probed videos **with full metadata**
- `skipped_items.csv` — articles/videos that were skipped (with reasons)
- Downloaded video files

### CSV Columns (video_index.csv & extracted_videos.csv)

The CSV files now include comprehensive article metadata:

| Column | Description |
|--------|-------------|
| `no` | Sequential number |
| `video_name` | Video title from yt-dlp |
| `link_article` | TurnBackHoax article URL |
| `link_video_asli` | Original video URL (Facebook, Instagram, TikTok, etc.) |
| `has_audio` | Boolean: video has audio track |
| `category` | Article category (Politik, Kesehatan, etc.) |
| `matched_keyword` | Keyword that matched (if keyword filtering used) |
| `snippet` | Text snippet around matched keyword |
| **`date`** | Article publication date (YYYY-MM-DD) |
| **`author`** | Author/source (usually "Mafindo") |
| **`image_url`** | Header image URL |
| **`narasi`** | Full narasi text (viral content description) |
| **`penjelasan`** | Full penjelasan text (fact-check explanation) |
| **`kesimpulan`** | Conclusion text (final verdict summary) |
| **`factcheck_result`** | Fact-check label: "Salah", "Benar", "Menyesatkan", etc. |
| **`factcheck_source`** | Source URL of checked content |
| **`references`** | Supporting references (URLs separated by `;`) |

**Bold fields** are newly added metadata extracted from article pages.

## Safety & etiquette

- Randomized delays between requests and downloads reduce load on target sites
- Do not pass personal account cookies unless necessary; use `--confirm-cookies` as a safety gate
- Respect site Terms of Service, copyright, and applicable laws

## Installing ffmpeg

**Windows**: Download from [gyan.dev](https://www.gyan.dev/ffmpeg/builds/) or [ffmpeg.org](https://ffmpeg.org/download.html), extract, and add the `bin` folder to your PATH.

**macOS**: `brew install ffmpeg`

**Linux**: `sudo apt install ffmpeg` (or equivalent for your distro)

Without ffmpeg, yt-dlp falls back to single-file formats (lower quality).
