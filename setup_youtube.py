"""
Setup YouTube OAuth - dijalankan manual di terminal (sekali saja).

    python setup_youtube.py login    # login interaktif, simpan token
    python setup_youtube.py status   # cek status token
    python setup_youtube.py logout   # hapus token
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from dotenv import load_dotenv
load_dotenv()

from src import yt_auth


def get_secrets_path():
    """Cari file client_secrets.json."""
    from config.settings import YOUTUBE_CLIENT_SECRETS
    cands = [YOUTUBE_CLIENT_SECRETS]
    # cari juga di storage/downloads
    dl = os.path.expanduser("~/storage/downloads")
    if os.path.isdir(dl):
        for f in os.listdir(dl):
            if f.startswith("client_secret") and f.endswith(".json"):
                cands.append(os.path.join(dl, f))
    for c in cands:
        if c and os.path.exists(c):
            return c
    return None


def main():
    cmd = sys.argv[1] if len(sys.argv) > 1 else "status"

    if cmd == "logout":
        yt_auth.clear()
        return

    if cmd == "status":
        p = yt_auth.token_path()
        if not yt_auth.has_token():
            print("❌ Belum ada token. Jalankan: python setup_youtube.py login")
            return
        try:
            creds = yt_auth.load_creds(get_secrets_path(), interactive=False)
            print("✅ Token valid")
            print("   expired :", creds.expired)
            print("   scopes  :", creds.scopes)
        except Exception as e:
            print("❌ Token tidak bisa dipakai:", str(e)[:150])
            print("   Jalankan ulang: python setup_youtube.py login")
        return

    # default: login
    print("=" * 62)
    print(" LOGIN YOUTUBE")
    print("=" * 62)
    secrets = get_secrets_path()
    if not secrets:
        print("❌ client_secrets.json tidak ditemukan.")
        print("   Taruh di config/yt_client_secrets.json atau Downloads.")
        return
    print(f"Client secrets: {secrets}")
    print()
    try:
        creds = yt_auth.load_creds(secrets, interactive=True)
        print()
        print("✅ Login berhasil, token tersimpan di", yt_auth.token_path())
        print("   Sekarang bot bisa upload ke YouTube tanpa interaksi.")
    except Exception as e:
        print("❌ Gagal:", str(e)[:200])


if __name__ == "__main__":
    main()
