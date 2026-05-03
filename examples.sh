#!/bin/bash
# Examples for using TurnBackHoax and DFK scrapers
# Run from the repo root directory

set -e

# Colors for output
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo -e "${BLUE}=== TurnBackHoax & DFK Scraper Examples ===${NC}\n"

# ============================================================================
# SETUP
# ============================================================================

echo -e "${YELLOW}1. INSTALLATION${NC}"
echo "   pip install -r requirements.txt"
echo "   # Optional: for dynamic/stealth fetchers"
echo "   pip install playwright && python -m playwright install chromium"
echo ""

# ============================================================================
# TURNBACKHOAX SCRAPER EXAMPLES
# ============================================================================

echo -e "${YELLOW}2. TURNBACKHOAX SCRAPER — Basic Usage${NC}"
echo "   cd scrapper"
echo "   python -m turnbackhoax.cli --start-page 1 --end-page 5"
echo ""

echo -e "${YELLOW}3. TURNBACKHOAX — Download specific pages${NC}"
echo "   python -m turnbackhoax.cli --start-page 1 --end-page 3 --download-dir ./videos"
echo ""
python -m /scrapper/turnbackhoax.cli --start-page 1 --end-page 3 --download-dir ./videos
echo -e "${YELLOW}4. TURNBACKHOAX — Keyword filtering${NC}"
echo "   # Find only articles about 'hoaks' (substring match)"
echo "   python -m turnbackhoax.cli \\
    --start-page 1 --end-page 10 \\
    --keyword hoaks \\
    --keyword-mode substring"
echo ""
echo "   # Find articles with BOTH 'covid' AND 'vaksin' (whole words)"
echo "   python -m turnbackhoax.cli \\
    --start-page 1 --end-page 10 \\
    --keyword covid \\
    --keyword vaksin \\
    --keyword-mode whole"
echo ""

echo -e "${YELLOW}5. TURNBACKHOAX — With authenticated platforms (Instagram, TikTok)${NC}"
echo "   # 1. Export cookies from your browser to cookies.txt (Netscape format)"
echo "   # 2. Run with:"
echo "   python -m turnbackhoax.cli \\
    --start-page 1 --end-page 5 \\
    --cookies ../cookies.txt \\
    --confirm-cookies"
echo ""

echo -e "${YELLOW}6. TURNBACKHOAX — Browser-based cookies (auto-extract from Chrome)${NC}"
echo "   python -m turnbackhoax.cli \\
    --start-page 1 --end-page 5 \\
    --cookies-from-browser chrome"
echo ""

echo -e "${YELLOW}7. TURNBACKHOAX — Resume interrupted run${NC}"
echo "   # First run (interrupted after page 3)"
echo "   python -m turnbackhoax.cli --start-page 1 --end-page 10"
echo ""
echo "   # Resume from where it stopped"
echo "   python -m turnbackhoax.cli --start-page 1 --end-page 10 --resume"
echo ""

echo -e "${YELLOW}8. TURNBACKHOAX — Dry run (probe but don't download)${NC}"
echo "   python -m turnbackhoax.cli \\
    --start-page 1 --end-page 2 \\
    --dry-run \\
    --log-level DEBUG"
echo ""

echo -e "${YELLOW}9. TURNBACKHOAX — Control concurrency & delays${NC}"
echo "   # 10 concurrent article fetches, 2 concurrent downloads"
echo "   python -m turnbackhoax.cli \\
    --start-page 1 --end-page 10 \\
    --concurrency 10 \\
    --download-concurrency 2 \\
    --min-delay-page 1.0 \\
    --max-delay-page 3.0 \\
    --min-delay-dl 2.0 \\
    --max-delay-dl 5.0"
echo ""

echo -e "${YELLOW}10. TURNBACKHOAX — JavaScript-rendered pages (slow)${NC}"
echo "   python -m turnbackhoax.cli \\
    --start-page 1 --end-page 3 \\
    --fetcher-mode dynamic"
echo ""

echo -e "${YELLOW}11. TURNBACKHOAX — Anti-bot stealth mode (very slow)${NC}"
echo "   python -m turnbackhoax.cli \\
    --start-page 1 --end-page 3 \\
    --fetcher-mode stealth"
echo ""

echo -e "${YELLOW}12. TURNBACKHOAX — Full-featured example${NC}"
echo "   python -m turnbackhoax.cli \\
    --start-page 1 \\
    --end-page 5 \\
    --download-dir ./turnback_output \\
    --keyword hoaks \\
    --keyword covid \\
    --keyword-mode substring \\
    --keyword-field both \\
    --show-snippet \\
    --skip-no-audio \\
    --concurrency 5 \\
    --download-concurrency 2 \\
    --min-delay-page 2.0 \\
    --max-delay-page 4.0 \\
    --min-delay-dl 5.0 \\
    --max-delay-dl 10.0 \\
    --fetcher-mode http \\
    --log-level INFO"
echo ""

echo -e "${YELLOW}13. TURNBACKHOAX — View outputs${NC}"
echo "   # CSVs are saved to download_dir:"
echo "   ls -lh downloaded_videos/"
echo "   # video_index.csv          — all videos found"
echo "   # extracted_videos.csv     — videos successfully probed"
echo "   # downloaded.csv           — videos successfully downloaded"
echo "   # skipped.csv              — videos that failed"
echo "   # checkpoint.json          — current progress (for --resume)"
echo ""

# ============================================================================
# DFK SCRAPER EXAMPLES
# ============================================================================

echo -e "${YELLOW}14. DFK DOWNLOADER — Basic usage${NC}"
echo "   cd scrapper/DFK"
echo "   python dfk_downloader.py \\
    --csv '~/Downloads/Konten_DFK.csv'"
echo ""

echo -e "${YELLOW}15. DFK — Download specific rows${NC}"
echo "   python dfk_downloader.py \\
    --csv '~/Downloads/Konten_DFK.csv' \\
    --start-row 100 \\
    --end-row 500"
echo ""

echo -e "${YELLOW}16. DFK — Filter by platform${NC}"
echo "   # Download only TikTok and Instagram content"
echo "   python dfk_downloader.py \\
    --csv '~/Downloads/Konten_DFK.csv' \\
    --platforms tiktok instagram"
echo ""

echo -e "${YELLOW}17. DFK — Resume interrupted download${NC}"
echo "   # First run"
echo "   python dfk_downloader.py --csv data.csv"
echo ""
echo "   # Resume from checkpoint"
echo "   python dfk_downloader.py --csv data.csv --resume"
echo ""

echo -e "${YELLOW}18. DFK — With browser cookies${NC}"
echo "   python dfk_downloader.py \\
    --csv data.csv \\
    --cookies-from-browser chrome"
echo ""

echo -e "${YELLOW}19. DFK — Control concurrency & retries${NC}"
echo "   python dfk_downloader.py \\
    --csv data.csv \\
    --concurrency 5 \\
    --max-retries 5 \\
    --retry-backoff 2.0 \\
    --min-delay 1.0 \\
    --max-delay 3.0"
echo ""

echo -e "${YELLOW}20. DFK — Dry run${NC}"
echo "   python dfk_downloader.py \\
    --csv data.csv \\
    --dry-run \\
    --log-level DEBUG"
echo ""

# ============================================================================
# OUTPUT FILES
# ============================================================================

echo -e "${YELLOW}21. Outputs from both scrapers${NC}"
echo ""
echo "   TurnBackHoax output:"
echo "   ├── downloaded_videos/"
echo "   │   ├── video_index.csv           (all found videos)"
echo "   │   ├── extracted_videos.csv      (successfully probed)"
echo "   │   ├── downloaded.csv            (successfully downloaded)"
echo "   │   ├── skipped.csv               (failed downloads)"
echo "   │   ├── checkpoint.json           (resume support)"
echo "   │   └── actual_video_files/"
echo ""
echo "   DFK output:"
echo "   ├── dfk_downloads/"
echo "   │   ├── dfk_downloaded.csv        (successful downloads)"
echo "   │   ├── dfk_failed.csv            (failed downloads)"
echo "   │   ├── dfk_checkpoint.json       (resume support)"
echo "   │   └── actual_video_files/"
echo ""

# ============================================================================
# SMART COOKIES BEHAVIOR
# ============================================================================

echo -e "${YELLOW}22. Understanding smart-cookies${NC}"
echo ""
echo "   Default (smart_cookies=True with --cookies):"
echo "   ├── Attempt 1: download WITHOUT cookies"
echo "   │   └── success? → DONE ✓"
echo "   │   └── auth error? → next"
echo "   │   └── other error? → FAIL ✗"
echo "   └── Attempt 2: download WITH cookies"
echo "       └── success? → DONE ✓"
echo "       └── fail? → FAIL ✗"
echo ""
echo "   With --no-smart-cookies:"
echo "   └── Always send cookies on every request"
echo ""
echo "   To disable:"
echo "   python -m turnbackhoax.cli \\
    --cookies cookies.txt \\
    --confirm-cookies \\
    --no-smart-cookies"
echo ""

# ============================================================================
# TROUBLESHOOTING
# ============================================================================

echo -e "${YELLOW}23. Troubleshooting${NC}"
echo ""
echo "   Problem: 'yt-dlp not found'"
echo "   Solution:"
echo "   python -m pip install --upgrade yt-dlp"
echo ""
echo "   Problem: 'playwright not installed'"
echo "   Solution (only needed for --fetcher-mode dynamic/stealth):"
echo "   pip install playwright"
echo "   python -m playwright install chromium"
echo ""
echo "   Problem: Instagram/TikTok downloads failing with 'login required'"
echo "   Solution: Export cookies and use --cookies + --confirm-cookies"
echo ""
echo "   Problem: Slow downloads"
echo "   Solution:"
echo "   - Increase --concurrency (fetch more articles in parallel)"
echo "   - Increase --download-concurrency (parallel yt-dlp processes)"
echo "   - Reduce --min-delay-* if rate-limiting isn't an issue"
echo ""

echo -e "${GREEN}=== Examples complete ===${NC}"
