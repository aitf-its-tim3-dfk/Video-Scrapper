import pandas as pd
import os
import re
import argparse
import logging
import unicodedata

# Konfigurasi Logging
logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')
logger = logging.getLogger(__name__)

def normalize_text(text):
    """Mengubah karakter spesial unicode ke bentuk standar (misal ² -> 2, …. -> ...)"""
    if not isinstance(text, str): return ""
    # Normalisasi unicode (NFKD) memisahkan karakter gabungan
    text = unicodedata.normalize('NFKD', text)
    # Ganti karakter spesifik yang sering muncul di hoax/sosmed
    replacements = {
        '²': '2', '¹': '1', '³': '3',
        '“': '"', '”': '"', '‘': "'", '’': "'",
        '…': '...', '—': '-'
    }
    for old, new in replacements.items():
        text = text.replace(old, new)
    return text

def sanitize(name):
    """Meniru cara yt-dlp --restrict-filenames membersihkan nama file"""
    s = normalize_text(name)
    # Ganti spasi dan karakter aneh dengan underscore
    s = re.sub(r'[^a-zA-Z0-9._-]', '_', s)
    # Satukan underscore beruntun
    s = re.sub(r'_+', '_', s)
    return s.strip('_')

def get_clean_words(name):
    """Mengambil kumpulan kata unik yang 'bermakna' dari judul"""
    s = normalize_text(name).lower()
    # Hapus metadata dinamis (views, reactions, dll)
    s = re.sub(r'\d+[mkb]?\s*(views|reactions|shares|comments|reactions|likes)', '', s)
    s = re.sub(r'\d+', '', s)
    # Ambil kata-kata alfanumerik saja yang panjangnya > 2
    words = re.findall(r'[a-z0-9]{3,}', s)
    # Buang kata-kata umum (noise)
    noise = {'video', 'reels', 'fyp', 'viral', 'trending', 'facebook', 'instagram', 'views', 'reactions', 'shares'}
    return set(w for w in words if w not in noise)

def run_mapping(target_dir, csv_filename='extracted_videos.csv'):
    csv_path = os.path.join(target_dir, csv_filename)
    
    # Cek subfolder video
    video_subfolder = None
    for folder_name in ['video', 'Videos', 'videos']:
        if os.path.isdir(os.path.join(target_dir, folder_name)):
            video_subfolder = folder_name
            break
    
    video_dir = os.path.join(target_dir, video_subfolder) if video_subfolder else target_dir
    video_subfolder = video_subfolder or ""

    if not os.path.exists(csv_path):
        logger.error(f"File CSV tidak ditemukan: {csv_path}")
        return

    try:
        df = pd.read_csv(csv_path)
    except Exception as e:
        logger.error(f"Gagal membaca CSV: {e}")
        return

    video_files = [f for f in os.listdir(video_dir) if f.lower().endswith(('.mp4', '.mkv', '.webm'))]
    if not video_files:
        logger.error(f"Tidak ada file video ditemukan di: {video_dir}")
        return

    logger.info(f"Memproses {len(df)} data CSV dan {len(video_files)} file video...")

    mapping = {}
    used_files = set()

    # Pass 1: Strict & Truncated Sanitized Match
    for f in video_files:
        name_on_disk = os.path.splitext(f)[0]
        san_disk = sanitize(name_on_disk).lower()
        for idx, row in df.iterrows():
            if row['no'] in mapping: continue
            san_csv = sanitize(str(row['video_name'])).lower()
            if san_csv == san_disk or san_csv.startswith(san_disk[:50]) or san_disk.startswith(san_csv[:50]):
                mapping[row['no']] = f
                used_files.add(f)
                break

    # Pass 2: Word Overlap Match (Fuzzy logic paling kuat)
    for f in video_files:
        if f in used_files: continue
        words_disk = get_clean_words(os.path.splitext(f)[0])
        if not words_disk: continue

        best_match_no = None
        max_overlap = 0

        for idx, row in df.iterrows():
            if row['no'] in mapping: continue
            words_csv = get_clean_words(str(row['video_name']))
            if not words_csv: continue

            # Hitung berapa banyak kata di disk yang ada di CSV
            overlap = len(words_disk.intersection(words_csv))
            if overlap > max_overlap:
                max_overlap = overlap
                best_match_no = row['no']

        # Jika overlap cukup besar (minimal 2 kata atau 40% dari kata di disk)
        if best_match_no and (max_overlap >= 3 or max_overlap/len(words_disk) >= 0.4):
            mapping[best_match_no] = f
            used_files.add(f)

    # Save Results
    df['actual_file'] = df['no'].map(mapping)
    df['actual_path'] = df['actual_file'].apply(lambda x: os.path.join(video_subfolder, x) if pd.notna(x) else '')
    output_path = os.path.join(target_dir, 'mapped_videos.csv')
    df.to_csv(output_path, index=False)
    
    success_count = df['actual_file'].notna().sum()
    logger.info("=" * 50)
    logger.info(f"HASIL AKHIR: {success_count} dari {len(df)} video terhubung.")
    logger.info(f"File CSV: {output_path}")
    logger.info("=" * 50)

    # Report Unmapped
    unmapped_csv = df[df['actual_file'].isna()]
    if not unmapped_csv.empty:
        logger.warning(f"\n[!] {len(unmapped_csv)} Record di CSV belum termapping.")
        for idx, row in unmapped_csv.head(10).iterrows():
            logger.warning(f"  - No {row['no']}: {row['video_name'][:70]}")

    unmapped_files = [f for f in video_files if f not in used_files]
    if unmapped_files:
        logger.warning(f"\n[!] {len(unmapped_files)} File di folder belum termapping.")
        for f in unmapped_files[:10]:
            logger.warning(f"  - {f}")

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("directory")
    parser.add_argument("--csv", default="extracted_videos.csv")
    args = parser.parse_args()
    run_mapping(args.directory, args.csv)
