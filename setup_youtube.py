"""
Setup YouTube OAuth untuk upload otomatis.
Jalankan: python setup_youtube.py

Yang perlu kamu lakukan (manual, di browser):
  1. https://console.cloud.google.com → Create Project
  2. Enable "YouTube Data API v3" (APIs & Services → Library)
  3. Setup OAuth consent screen (External, isi app name + email)
  4. Credentials → Create Credentials → OAuth client ID → Desktop app
  5. Download JSON → simpan sebagai config/yt_client_secrets.json
  6. Jalankan script ini → akan muncul link untuk login
"""

import os
import sys
import json
import requests

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from config.settings import YOUTUBE_CLIENT_SECRETS

API_KEY_ENV = "YOUTUBE_API_KEY"


def cek_file():
    print("=" * 60)
    print("  SETUP YOUTUBE UPLOAD")
    print("=" * 60)
    print(f"\n1️⃣  Cek file OAuth client...")
    if os.path.exists(YOUTUBE_CLIENT_SECRETS):
        print(f"   ✅ {YOUTUBE_CLIENT_SECRETS} ditemukan")
        try:
            with open(YOUTUBE_CLIENT_SECRETS) as f:
                d = json.load(f)
            info = d.get("installed") or d.get("web") or d
            print(f"      client_id : {info.get('client_id', '?')[:30]}...")
            print(f"      project   : {info.get('project_id', '?')}")
        except Exception as e:
            print(f"      ⚠️  Gagal parse: {e}")
        return True

    print(f"   ❌ {YOUTUBE_CLIENT_SECRETS} belum ada\n")
    print("   Buat di browser:")
    print("   a) https://console.cloud.google.com → Create Project")
    print("   b) APIs & Services → Library → search 'YouTube Data API v3' → Enable")
    print("   c) APIs & Services → OAuth consent screen → Configure")
    print("      → User type: External")
    print("      → App name: apa aja (mis. 'Autopilot Content')")
    print("      → Developer email: email kamu")
    print("      → Tambah test email kamu")
    print("   d) APIs & Services → Credentials → Create Credentials")
    print("      → OAuth client ID → Application type: Desktop app → Create")
    print(f"   e) Download JSON → rename & simpan ke: {YOUTUBE_CLIENT_SECRETS}")
    print("      (downloadnya ada di folder Downloads HP)")
    return False


def cek_api_key():
    """Cek quota YouTube API (opsional, untuk monitoring)."""
    key = os.getenv(API_KEY_ENV, "")
    if not key:
        print(f"\n2️⃣  {API_KEY_ENV} belum di-set (opsional, buat cek quota aja)")
        return
    r = requests.get("https://www.googleapis.com/youtube/v3/videos",
                     params={"part": "snippet", "mine": True, "maxResults": 1, "key": key},
                     timeout=20, headers={"User-Agent": "Mozilla/5.0"})
    print(f"\n2️⃣  API key → status {r.status_code}")
    if r.status_code == 200:
        print(f"   Channel kamu: {r.json().get('items', [{}])[0].get('snippet', {}).get('channelTitle', '?')}")


def login():
    """Login interaktif (OOB flow) dan simpan token."""
    print(f"\n3️⃣  Login Google...")
    try:
        from src.upload import _login_youtube_interactive
    except Exception as e:
        print(f"   ❌ Import gagal: {e}")
        return False

    scopes = ["https://www.googleapis.com/auth/youtube.upload"]
    try:
        creds = _login_youtube_interactive(scopes, YOUTUBE_CLIENT_SECRETS)
    except Exception as e:
        print(f"\n   ❌ Login gagal: {e}")
        print("\n   Kemungkinan:")
        print("   - Code salah/kedaluwarsa (code expire dalam 10 menit)")
        print("   - Browser tidakauthorize dengan akun yang benar")
        return False

    import pickle
    token_file = "config/yt_token.pickle"
    os.makedirs("config", exist_ok=True)
    with open(token_file, "wb") as f:
        pickle.dump(creds, f)
    print(f"\n   ✅ Token disimpan: {token_file}")
    print(f"   Refresh token: {'ada ✅' if creds.refresh_token else 'tidak ❌'}")
    if not creds.refresh_token:
        print("   ⚠️  Tanpa refresh token, kamu harus login ulang tiap ~1 jam")
    return True


def test_upload():
    """Test upload video kecil untuk verifikasi."""
    print(f"\n4️⃣  Test upload...")
    import glob
    videos = sorted(glob.glob("output/videos/*.mp4"), key=os.path.getmtime)
    if not videos:
        print("   ⚠️  Belum ada video di output/videos/. Generate dulu.")
        return
    path = videos[-1]
    print(f"   Video: {path}")
    print("   (upload sungguhan ke channel kamu, video akan tayang)")
    jawab = input("   Lanjut upload? (y/n): ").strip().lower()
    if jawab != "y":
        print("   Dibatalkan.")
        return

    from src.upload import upload_youtube
    try:
        url = upload_youtube(
            video_path=path,
            judul="Test Upload - Autopilot Content",
            deskripsi="Video test dari autopilot-content bot.",
            tags=["test", "autopilot"],
        )
        print(f"\n   ✅ BERHASIL: {url}")
    except Exception as e:
        print(f"\n   ❌ Gagal: {e}")


if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else "all"

    if not cek_file():
        print("\n❌ File OAuth client belum ada. Selesaikan langkah di atas dulu.")
        sys.exit(1)

    cek_api_key()

    if cmd in ("all", "login"):
        if not login():
            sys.exit(1)

    if cmd in ("all", "test"):
        test_upload()
