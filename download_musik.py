"""
Download musik bebas copyright untuk background video.
Sumber: YouTube (search "royalty free / copyright free music").
Jalankan: python download_musik.py [jumlah]
"""

import os
import subprocess
import sys

MUSIK_DIR = "musik"
NODE_PATH = "/data/data/com.termux/files/usr/bin/node"

# Query - hasilnya bebas copyright untuk dipakai di YouTube/Facebook
QUERIES = [
    "royalty free ambient background music no copyright",
    "copyright free inspirational cinematic music",
    "no copyright peaceful piano relaxing music",
]

# Durasi maksimal (detik) - musik terlalu panjang bikin render lama
MAX_DURATION = 600


def run_ytdlp(args, timeout=300):
    cmd = [
        "yt-dlp",
        "--js-runtimes", f"node:{NODE_PATH}",
        "--no-playlist", "--quiet", "--no-warnings",
        "--socket-timeout", "30",
        "--retries", "3",
    ] + args
    return subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)


def get_candidates(query, max_results=5):
    """Cari kandidat video dari YouTube."""
    try:
        res = run_ytdlp(
            ["--flat-playlist", "--get-id", f"ytsearch{max_results}:{query}"],
            timeout=90,
        )
        if res.returncode != 0:
            return []
        return [l.strip() for l in res.stdout.splitlines() if l.strip()]
    except Exception as e:
        print(f"  Search error: {e}")
        return []


def download_one(video_id, idx):
    """Download satu video jadi mp3. Return path file atau None."""
    url = f"https://www.youtube.com/watch?v={video_id}"
    # Pakai prefix unik supaya file tidak saling timpa
    out_tpl = f"{MUSIK_DIR}/{idx:02d}_%(title)s.%(ext)s"
    try:
        res = run_ytdlp([
            "-f", "bestaudio",
            "-x", "--audio-format", "mp3", "--audio-quality", "0",
            "--match-filter", f"duration < {MAX_DURATION}",
            "-o", out_tpl,
            url,
        ])
        if res.returncode == 0:
            return True
    except Exception as e:
        print(f"  Download error: {e}")
    return False


def download_musik(jumlah=5):
    os.makedirs(MUSIK_DIR, exist_ok=True)

    existing = [f for f in os.listdir(MUSIK_DIR) if f.endswith(".mp3")]
    if len(existing) >= jumlah:
        print(f"[Musik] Sudah ada {len(existing)} file di '{MUSIK_DIR}/', skip download.")
        for f in existing:
            print(f"  - {f}")
        return

    print(f"[Musik] Cari & download {jumlah} musik bebas copyright dari YouTube...")
    print(f"[Musik] Target folder: {MUSIK_DIR}/\n")

    berhasil = 0
    idx = len(existing)
    for query in QUERIES:
        if berhasil >= jumlah:
            break

        print(f"[Musik] Search: '{query}'")
        candidates = get_candidates(query)
        if not candidates:
            print("  Tidak ada kandidat, lanjut query berikutnya")
            continue

        for vid in candidates:
            if berhasil >= jumlah:
                break
            idx += 1
            print(f"  Coba: {vid}")
            if download_one(vid, idx):
                print(f"  OK")
                berhasil += 1
            else:
                print(f"  Gagal (video tidak tersedia / durasi kepanjangan)")

    print(f"\n[Musik] Selesai! {berhasil}/{jumlah} musik berhasil.")
    files = sorted(f for f in os.listdir(MUSIK_DIR) if f.endswith(".mp3"))
    for f in files:
        size_mb = os.path.getsize(os.path.join(MUSIK_DIR, f)) / (1024*1024)
        print(f"  - {f} ({size_mb:.1f} MB)")


if __name__ == "__main__":
    n = int(sys.argv[1]) if len(sys.argv) > 1 else 5
    download_musik(n)
