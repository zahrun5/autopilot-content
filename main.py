"""
Main Pipeline - Autopilot Quotes Video Generator
Jalankan: python main.py --niche motivasi --topik "pantang menyerah"
"""

import argparse
import os
import re
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Pastikan cwd = folder project agar path relatif (output/, musik/) konsisten
os.chdir(os.path.dirname(os.path.abspath(__file__)))

from src.llm import generate_script
from src.pixabay import fetch_semua_foto
from src.video import buat_video
from src.upload import upload_semua
from config.settings import NICHE_OPTIONS, VIDEO_DIR, MUSIK_DIR


def sanitize_filename(text: str) -> str:
    text = text.lower().strip()
    text = re.sub(r"[^\w\s-]", "", text)
    text = re.sub(r"[\s]+", "_", text)
    return text[:60]


def run_pipeline(niche="motivasi", topik=None, skip_upload=False):
    start = time.time()
    print("\n" + "="*60)
    print("  AUTOPILOT QUOTES VIDEO")
    print("="*60)
    print(f"  Niche  : {NICHE_OPTIONS.get(niche, niche)}")
    print(f"  Topik  : {topik or '(auto)'}")
    print(f"  Upload : {'tidak' if skip_upload else 'YouTube + Facebook'}")
    print("="*60 + "\n")

    # ── STEP 1: Generate quotes via LLM ──────────────────────
    print("[STEP 1/4] Generate quotes...")
    script = generate_script(niche=niche, topik=topik)
    print(f"  Judul  : {script['judul']}")
    print(f"  Quotes : {len(script['slides'])}\n")

    # ── STEP 2: Fetch foto dari Pixabay ───────────────────────
    print("[STEP 2/4] Fetch foto dari Pixabay...")
    foto_paths = fetch_semua_foto(script["slides"])
    print(f"  {len(foto_paths)} foto berhasil didownload\n")

    # ── STEP 3: Render video ──────────────────────────────────
    print("[STEP 3/4] Render video...")

    # Cek musik
    import glob
    musik_files = glob.glob(os.path.join(MUSIK_DIR, "*.mp3")) + \
                  glob.glob(os.path.join(MUSIK_DIR, "*.m4a"))
    if not musik_files:
        print(f"  [!] Tidak ada musik di folder '{MUSIK_DIR}/'")
        print(f"  [!] Download dari YouTube Audio Library lalu taruh di sana.")
        print(f"  [!] Video akan dibuat tanpa musik.\n")
    else:
        print(f"  Musik   : {os.path.basename(musik_files[0])} (+{len(musik_files)-1} lainnya)\n")

    filename = sanitize_filename(script["judul"]) + ".mp4"
    video_path = buat_video(
        slides=script["slides"],
        foto_paths=foto_paths,
        output_filename=filename,
    )
    print(f"  Video  : {video_path}\n")

    # ── STEP 4: Upload ────────────────────────────────────────
    hasil_upload = {}
    if not skip_upload:
        print("[STEP 4/4] Upload ke YouTube & Facebook...")
        hasil_upload = upload_semua(video_path=video_path, script=script)
    else:
        print("[STEP 4/4] Upload dilewati (--no-upload)\n")

    # ── SUMMARY ───────────────────────────────────────────────
    elapsed = time.time() - start
    print("\n" + "="*60)
    print("  SELESAI!")
    print("="*60)
    print(f"  Durasi proses : {elapsed/60:.1f} menit")
    print(f"  Video         : {video_path}")
    if hasil_upload.get("youtube"):
        print(f"  YouTube       : {hasil_upload['youtube']}")
    if hasil_upload.get("facebook"):
        print(f"  Facebook      : {hasil_upload['facebook']}")
    for plat, err in (hasil_upload.get("errors") or {}).items():
        print(f"  [!] {plat} gagal: {str(err)[:120]}")
    print("="*60 + "\n")

    return {"script": script, "video_path": video_path, "upload": hasil_upload}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Autopilot Quotes Video - Generate & upload otomatis"
    )
    parser.add_argument(
        "--niche",
        choices=list(NICHE_OPTIONS.keys()),
        default="motivasi",
        help=f"Pilih niche: {', '.join(NICHE_OPTIONS.keys())}",
    )
    parser.add_argument(
        "--topik", type=str, default=None,
        help="Topik spesifik (opsional)",
    )
    parser.add_argument(
        "--no-upload", action="store_true",
        help="Skip upload, hanya generate video lokal",
    )
    args = parser.parse_args()
    run_pipeline(niche=args.niche, topik=args.topik, skip_upload=args.no_upload)
