#!/usr/bin/env python3
"""Regenerate CSV files from checkpoint JSON."""
import csv
import json
import os
import sys

def regenerate_csv(checkpoint_file='dfk_checkpoint.json', download_dir='dfk_downloads'):
    """Regenerate CSV files from checkpoint."""
    
    # Load checkpoint
    if not os.path.exists(checkpoint_file):
        print(f"ERROR: Checkpoint file not found: {checkpoint_file}")
        sys.exit(1)
    
    with open(checkpoint_file, 'r', encoding='utf-8') as f:
        data = json.load(f)
    
    downloaded = data.get('downloaded', [])
    failed = data.get('failed', [])
    
    print(f"Loaded checkpoint:")
    print(f"  Downloaded: {len(downloaded)}")
    print(f"  Failed: {len(failed)}")
    
    os.makedirs(download_dir, exist_ok=True)
    
    # Export downloaded
    if downloaded:
        csv_path = os.path.join(download_dir, 'dfk_downloaded.csv')
        with open(csv_path, 'w', encoding='utf-8', newline='') as f:
            writer = csv.DictWriter(f, fieldnames=[
                'row_num', 'url', 'platform', 'category', 'date',
                'output_path', 'attempt',
            ])
            writer.writeheader()
            for item in downloaded:
                writer.writerow({
                    'row_num': item.get('row_num'),
                    'url': item.get('url'),
                    'platform': item.get('platform'),
                    'category': item.get('category'),
                    'date': item.get('date'),
                    'output_path': item.get('output_path'),
                    'attempt': item.get('attempt'),
                })
        print(f"\n✓ Exported {len(downloaded)} downloads to {csv_path}")
    
    # Export failed
    if failed:
        csv_path = os.path.join(download_dir, 'dfk_failed.csv')
        with open(csv_path, 'w', encoding='utf-8', newline='') as f:
            writer = csv.DictWriter(f, fieldnames=[
                'row_num', 'url', 'platform', 'category', 'date',
                'error', 'attempts',
            ])
            writer.writeheader()
            for item in failed:
                writer.writerow({
                    'row_num': item.get('row_num'),
                    'url': item.get('url'),
                    'platform': item.get('platform'),
                    'category': item.get('category'),
                    'date': item.get('date'),
                    'error': item.get('error'),
                    'attempts': item.get('attempts'),
                })
        print(f"✓ Exported {len(failed)} failures to {csv_path}")
    
    print("\n" + "=" * 60)
    print("SUMMARY")
    print(f"  Total downloaded: {len(downloaded)}")
    print(f"  Total failed: {len(failed)}")
    print(f"  Total processed: {len(downloaded) + len(failed)}")
    print("=" * 60)

if __name__ == '__main__':
    regenerate_csv()
