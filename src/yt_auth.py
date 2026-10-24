"""
YouTube OAuth helper.

Pisahkan login interaktif dari proses upload supaya bot Telegram tidak
perlu terminal untuk input kode. Login dilakukan sekali lewat CLI
(python setup_youtube.py login), lalu token disimpan di
config/yt_token.pickle dan dipakai ulang (di-refresh otomatis).
"""

import os
import pickle
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

PROJECT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TOKEN_FILE = os.path.join(PROJECT_DIR, "config", "yt_token.pickle")
SCOPES = ["https://www.googleapis.com/auth/youtube.upload"]


def token_path():
    return os.path.join(PROJECT_DIR, "config", "yt_token.pickle")


def has_token():
    return os.path.exists(token_path())


def load_creds(client_secrets_path=None, interactive=True):
    """
    Ambil kredensial YouTube.

    - Kalau token ada & valid -> pakai
    - Kalau token ada & expired tapi punya refresh_token -> refresh
    - Kalau tidak ada -> login interaktif (hanya kalau interactive=True)

    Returns: credentials object, atau None kalau tidak bisa.
    """
    from google.oauth2.credentials import Credentials
    from google.auth.transport.requests import Request

    path = token_path()
    creds = None

    if os.path.exists(path):
        try:
            with open(path, "rb") as f:
                creds = pickle.load(f)
        except Exception as e:
            print(f"[YouTube] Gagal baca token: {e}")
            creds = None

    if creds and creds.valid:
        return creds

    if creds and creds.expired and creds.refresh_token:
        try:
            creds.refresh(Request())
            _save(creds)
            print("[YouTube] Token di-refresh otomatis.")
            return creds
        except Exception as e:
            print(f"[YouTube] Refresh gagal: {e}")
            creds = None

    # Perlu login baru
    if not interactive:
        raise RuntimeError(
            "Token YouTube belum ada / expired. "
            "Jalankan sekali: python setup_youtube.py login"
        )

    if not client_secrets_path or not os.path.exists(client_secrets_path):
        raise RuntimeError(
            f"File OAuth client tidak ditemukan: {client_secrets_path}. "
            "Download dari Google Cloud Console."
        )

    from src.upload import _login_youtube_interactive
    creds = _login_youtube_interactive(SCOPES, client_secrets_path)
    _save(creds)
    return creds


def _save(creds):
    os.makedirs(os.path.dirname(token_path()), exist_ok=True)
    with open(token_path(), "wb") as f:
        pickle.dump(creds, f)
    os.chmod(token_path(), 0o600)
    print(f"[YouTube] Token disimpan: {token_path()}")


def clear():
    """Hapus token (untuk logout)."""
    p = token_path()
    if os.path.exists(p):
        os.remove(p)
        print("[YouTube] Token dihapus.")
        return True
    return False


if __name__ == "__main__":
    from config.settings import YOUTUBE_CLIENT_SECRETS
    if len(sys.argv) > 1 and sys.argv[1] == "clear":
        clear()
    else:
        c = load_creds(YOUTUBE_CLIENT_SECRETS, interactive=True)
        print("✅ Cred siap:", c.token_uri if c else None)
