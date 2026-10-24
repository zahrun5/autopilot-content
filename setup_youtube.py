"""
Setup YouTube OAuth - dijalankan manual di terminal (sekali saja).

    python setup_youtube.py login    # login interaktif, simpan token
    python setup_youtube.py import   # import credential dari project ytbot
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
        for f in sorted(os.listdir(dl)):
            if f.startswith("client_secret") and f.endswith(".json"):
                cands.append(os.path.join(dl, f))
    for c in cands:
        if c and os.path.exists(c):
            return c
    return None


def cmd_import():
    """Import credential dari project ytbot."""
    print("=" * 62)
    print(" IMPORT CREDENTIAL DARI YTBOT")
    print("=" * 62)
    ok, msg = yt_auth.import_from_ytbot()
    print(msg)
    if ok:
        print()
        print("Status:", yt_auth.status())
    return ok


def cmd_status():
    if not yt_auth.has_token():
        print("❌ Belum ada token.")
        print("   → python setup_youtube.py import   (dari ytbot)")
        print("   → python setup_youtube.py login    (login baru)")
        return
    print(yt_auth.status())
    try:
        creds = yt_auth.load_creds(get_secrets_path(), interactive=False)
        print("   client_id :", creds.client_id[:35] + "...")
    except Exception as e:
        print("❌ Token tidak bisa dipakai:", str(e)[:150])


def cmd_login():
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


def main():
    cmd = sys.argv[1] if len(sys.argv) > 1 else "status"
    if cmd == "logout":
        yt_auth.clear()
    elif cmd == "status":
        cmd_status()
    elif cmd == "import":
        cmd_import()
    elif cmd == "login":
        cmd_login()
    else:
        print(f"Unknown command: {cmd}")
        print(__doc__)


if __name__ == "__main__":
    main()
