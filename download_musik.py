"""
Download musik background gratis - Creative Commons
Jalankan: python download_musik.py
"""

import subprocess
import os
import glob

MUSIK_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "musik")
os.makedirs(MUSIK_DIR, exist_ok=True)

# Playlist YouTube Audio Library (CC / royalty-free, aman monetisasi)
# Semua adalah track instrumental pendek 2-5 menit
PLAYLIST_URLS = [
    # YouTube Audio Library - Ambient/Calm
    "https://www.youtube.com/playlist?list=PLzCxunOM5WFKZuBXSoKoKzgCHOCMNrXHB",
    # YouTube Audio Library - Inspirational
    "https://www.youtube.com/playlist?list=PLzCxunOM5WFJGneBZgKvGMEWKHtKS7gIg",
]

# Alternatif: download per-track langsung
TRACK_URLS = [
    "https://www.youtube.com/watch?v=EkDtzMwqMpk",   # peaceful ambient
    "https://www.youtube.com/watch?v=n61ULEU7CO0",   # soft piano
    "https://www.youtube.com/watch?v=mDdSlG3M6p4",   # calm instrumental
    "https://www.youtube.com/watch?v=OiDMRM_ot4I",   # gentle acoustic
    "https://www.youtube.com/watch?v=M8eItITv8QA",   # relaxing background
]

def download_track(url: str, index: int) -> bool:
    output_template = os.path.join(MUSIK_DIR, f"musik_{index:02d}.%(ext)s")
    cmd = [
        "yt-dlp",
        "-x",
        "--audio-format", "mp3",
        "--audio-quality", "5",          # 128kbps cukup untuk background
        "-o", output_template,
        "--no-playlist",
        "--match-filter", "duration < 600 & duration > 60",
        "--quiet", "--no-warnings",
        url,
    ]
    print(f"[Musik] Downloading ({index+1}/{len(TRACK_URLS)}): {url}")
    result = subprocess.run(cmd, timeout=120)
    return result.returncode == 0


if __name__ == "__main__":
    print(f"Downloading {len(TRACK_URLS)} lagu ke: {MUSIK_DIR}/\n")
    sukses = 0
    for i, url in enumerate(TRACK_URLS):
        try:
            if download_track(url, i):
                sukses += 1
                print(f"  OK\n")
            else:
                print(f"  GAGAL\n")
        except Exception as e:
            print(f"  ERROR: {e}\n")

    files = glob.glob(os.path.join(MUSIK_DIR, "*.mp3"))
    print(f"Selesai! {sukses}/{len(TRACK_URLS)} berhasil.")
    print(f"Total file: {len(files)}")
    for f in files:
        size = os.path.getsize(f) / (1024 * 1024)
        print(f"  {os.path.basename(f)} - {size:.1f} MB")
