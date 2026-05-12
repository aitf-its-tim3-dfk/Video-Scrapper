#!/usr/bin/env python3
"""Upload downloaded videos to a HuggingFace Dataset repo.

Usage:
    python upload_to_hf.py \
        --source-dir /tmp/tbh_output \
        --repo-id your-org/turnbackhoax-videos \
        --token hf_xxx \
        --run-label pages-1-50
"""
import argparse
import logging
import os
import sys

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)

VIDEO_EXT = {".mp4", ".mkv", ".webm", ".mov", ".avi", ".flv", ".m4v"}


def parse_args():
    p = argparse.ArgumentParser()
    p.add_argument("--source-dir", required=True, help="Local folder with downloaded videos")
    p.add_argument("--repo-id",    default="farwew/aitf-scrap", help="HuggingFace repo: org/dataset-name")
    p.add_argument("--token",      default=os.environ.get("HF_TOKEN"), help="HF write token")
    p.add_argument("--run-label",  default="batch", help="Subfolder name inside the HF repo")
    p.add_argument("--private",    action="store_true", help="Create repo as private (default: public)")
    return p.parse_args()


def main():
    args = parse_args()

    if not args.token:
        logger.error("No HuggingFace token. Set --token or HF_TOKEN env var.")
        sys.exit(1)

    try:
        from huggingface_hub import HfApi
    except ImportError:
        logger.error("huggingface_hub not installed. Run: pip install huggingface_hub")
        sys.exit(1)

    api = HfApi(token=args.token)

    # Create repo if it doesn't exist yet
    try:
        api.create_repo(
            repo_id=args.repo_id,
            repo_type="dataset",
            private=args.private,
            exist_ok=True,
        )
        logger.info("Repo ready: %s", args.repo_id)
    except Exception as exc:
        logger.error("Failed to create/access repo: %s", exc)
        sys.exit(1)

    # Count video files
    video_files = [
        f for f in os.listdir(args.source_dir)
        if os.path.splitext(f)[1].lower() in VIDEO_EXT
    ]
    logger.info("Found %d video files to upload from %s", len(video_files), args.source_dir)

    if not video_files:
        logger.info("Nothing to upload.")
        return

    # Upload entire folder (videos only) to repo subfolder
    # Non-video files (CSVs, checkpoint) are ignored via ignore_patterns
    path_in_repo = args.run_label  # e.g. "pages-1-50/"

    logger.info("Uploading to %s/%s ...", args.repo_id, path_in_repo)
    try:
        api.upload_folder(
            folder_path=args.source_dir,
            repo_id=args.repo_id,
            repo_type="dataset",
            path_in_repo=path_in_repo,
            ignore_patterns=["*.json", "*.csv", "*.txt"],
            commit_message=f"Add videos: {args.run_label}",
        )
        logger.info("Upload complete: https://huggingface.co/datasets/%s", args.repo_id)
    except Exception as exc:
        logger.error("Upload failed: %s", exc)
        sys.exit(1)


if __name__ == "__main__":
    main()
