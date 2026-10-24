"""
YouTube OAuth helper.

Pisahkan login interaktif dari proses upload supaya bot Telegram tidak
perlu terminal untuk input kode. Login dilakukan sekali lewat CLI
(python setup_youtube.py login), lalu token disimpan dan dipakai ulang
(di-refresh otomatis).

Format token: JSON (sama seperti google-auth token file standar).
Lokasi : config/yt_token.json
"""

import json
import os
import pickle
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

PROJECT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CONFIG_DIR = os.path.join(PROJECT_DIR, "config")
TOKEN_FILE = os.path.join(CONFIG_DIR, "yt_token.json")
LEGACY_PICKLE = os.path.join(CONFIG_DIR, "yt_token.pickle")
SCOPES = ["https://www.googleapis.com/auth/youtube.upload"]

# Credential dari project ytbot (kalau ada) - dipakai sebagai fallback
YTBOT_DIR = os.path.expanduser("~/ytbot")


def token_path():
    return TOKEN_FILE


def has_token():
    return os.path.exists(TOKEN_FILE) or os.path.exists(LEGACY_PICKLE)


def _load_from_disk():
    """Baca token dari disk. Coba JSON dulu, lalu pickle legacy."""
    from google.oauth2.credentials import Credentials

    if os.path.exists(TOKEN_FILE):
        try:
            return Credentials.from_authorized_user_file(TOKEN_FILE, SCOPES)
        except Exception as e:
            print(f"[YouTube] Gagal baca token JSON: {e}")

    if os.path.exists(LEGACY_PICKLE):
        try:
            with open(LEGACY_PICKLE, "rb") as f:
                return pickle.load(f)
        except Exception as e:
            print(f"[YouTube] Gagal baca token pickle: {e}")

    return None


def _save(creds):
    """Simpan token (JSON) + refresh bila perlu."""
    os.makedirs(CONFIG_DIR, exist_ok=True)
    payload = creds.to_json()
    with open(TOKEN_FILE, "w") as f:
        f.write(payload)
    os.chmod(TOKEN_FILE, 0o600)
    if os.path.exists(LEGACY_PICKLE):
        try:
            os.remove(LEGACY_PICKLE)
        except OSError:
            pass
    print(f"[YouTube] Token disimpan: {TOKEN_FILE}")


def import_from_ytbot():
    """
    Import credential dari project ytbot (~/.ytbot / ~/ytbot).

   ytbot punya OAuth client bertipe Desktop app + token.json yang
    sudah working. Menghemat waktu login ulang.

    Returns: (berhasil, pesan)
    """
    if not os.path.isdir(YTBOT_DIR):
        return False, f"Folder {YTBOT_DIR} tidak ada"

    src_client = os.path.join(YTBOT_DIR, "client_secret.json")
    src_token = os.path.join(YTBOT_DIR, "token.json")

    if not os.path.exists(src_token):
        return False, f"Token tidak ditemukan: {src_token}"

    # Copy client secrets (kalau autopilot belum punya yang tipe Desktop app)
    if os.path.exists(src_client):
        dst_client = os.path.join(CONFIG_DIR, "yt_client_secrets.json")
        need_copy = True
        if os.path.exists(dst_client):
            try:
                with open(dst_client, encoding="utf-8") as f:
                    kind = list(json.load(f).keys())[0]
                if kind == "installed":
                    print("[YouTube] Client secrets sudah benar (Desktop app), tidak ditimpa")
                    need_copy = False
                else:
                    print(f"[YouTube] Client secrets lama bertipe '{kind}', diganti ke Desktop app")
            except Exception:
                pass
        if need_copy:
            import shutil
            os.makedirs(CONFIG_DIR, exist_ok=True)
            shutil.copy2(src_client, dst_client)
            print(f"[YouTube] Client secrets dicopy: {dst_client}")

    # Copy token
    import shutil
    shutil.copy2(src_token, TOKEN_FILE)
    os.chmod(TOKEN_FILE, 0o600)
    print(f"[YouTube] Token dicopy: {TOKEN_FILE}")

    return True, f"✅ Credential ytbot berhasil di-import"


def load_creds(client_secrets_path=None, interactive=True):
    """
    Ambil kredensial YouTube.

    - Token ada & valid -> pakai
    - Token ada & expired tapi punya refresh_token -> refresh
    - Tidak ada -> login interaktif (hanya kalau interactive=True)

    Returns: credentials object
    """
    from google.auth.transport.requests import Request

    creds = _load_from_disk()

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

    # Coba import dari ytbot sebagai-automatic
    ok, msg = import_from_ytbot()
    if ok:
        creds = _load_from_disk()
        if creds:
            if creds.expired and creds.refresh_token:
                try:
                    creds.refresh(Request())
                    _save(creds)
                except Exception as e:
                    print(f"[YouTube] Refresh token ytbot gagal: {e}")
            if creds.valid:
                print("[YouTube] ✅ Credential ytbot dipakai & valid.")
                return creds

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


def clear():
    """Hapus token (untuk logout)."""
    removed = False
    for p in (TOKEN_FILE, LEGACY_PICKLE):
        if os.path.exists(p):
            os.remove(p)
            removed = True
    if removed:
        print("[YouTube] Token dihapus.")
        return True
    return False


def status():
    """Ringkasan status token."""
    from google.auth.transport.requests import Request

    creds = _load_from_disk()
    if not creds:
        return "❌ Belum ada token"
    info = f"expired={creds.expired} | refresh_token={'ada' if creds.refresh_token else 'tidak'}"
    if creds.expired and creds.refresh_token:
        try:
            creds.refresh(Request())
            _save(creds)
            info += " | ✅ (sudah di-refresh)"
        except Exception as e:
            info += f" | ❌ refresh gagal: {str(e)[:60]}"
    elif creds.valid:
        info += " | ✅ valid"
    return info


if __name__ == "__main__":
    from config.settings import YOUTUBE_CLIENT_SECRETS
    if len(sys.argv) > 1 and sys.argv[1] == "clear":
        clear()
    elif len(sys.argv) > 1 and sys.argv[1] == "import":
        print(import_from_ytbot()[1])
    else:
        print(status())
