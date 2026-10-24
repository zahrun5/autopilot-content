"""
Facebook token helper - refresh otomatis page access token.

Token Facebook punya masa berlaku. Kalau APP_ID + APP_SECRET tersedia,
token bisa di-refresh sendiri tanpa campur tangan user.
"""

import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv
load_dotenv()

API = "https://graph.facebook.com/v18.0"
H = {"User-Agent": "Mozilla/5.0 (Linux; Android) autopilot-content/1.0"}


def _env():
    """Baca dari .env langsung supaya nilai terbaru selalu dipakai."""
    from src.env_manager import get
    page_id = get("FACEBOOK_PAGE_ID")
    token = get("FACEBOOK_ACCESS_TOKEN")
    if not page_id or not token:
        from config.settings import FACEBOOK_PAGE_ID, FACEBOOK_ACCESS_TOKEN
        page_id = page_id or FACEBOOK_PAGE_ID
        token = token or FACEBOOK_ACCESS_TOKEN
    return page_id, token


def _app_creds():
    from src.env_manager import get
    app_id = get("FACEBOOK_APP_ID") or os.getenv("FACEBOOK_APP_ID", "")
    app_secret = get("FACEBOOK_APP_SECRET") or os.getenv("FACEBOOK_APP_SECRET", "")
    return app_id, app_secret


def get_page_token(page_id=None, token=None, attempts=2):
    """
    Ambil page access token yang valid.

    Urutan:
    1. Cek token sekarang masih bisa akses page
    2. Kalau expired & ada APP_ID/SECRET -> tukar ke long-lived token
    3. Kalau masih gagal -> coba dari user token baru

    Returns: (token_baru, pesan)
    """
    import requests

    page_id = page_id or _env()[0]
    token = token or _env()[1]

    if not page_id or not token:
        return None, "FACEBOOK_PAGE_ID / FACEBOOK_ACCESS_TOKEN belum diisi"

    for attempt in range(1, attempts + 1):
        ok, msg = _cek_token(page_id, token)
        if ok:
            return token, msg

        print(f"[Facebook] Attempt {attempt}: {msg}")

        # Coba refresh dari app secret
        app_id, app_secret = _app_creds()
        if app_id and app_secret:
            new_tok = _long_lived(token, app_id, app_secret)
            if new_tok:
                # tukar user token -> page token
                pt = _exchange_page_token(new_tok, page_id)
                if pt:
                    _save(page_id, pt)
                    ok2, msg2 = _cek_token(page_id, pt)
                    if ok2:
                        return pt, "✅ Token di-refresh otomatis"
                token = new_tok
                continue

        break

    return None, msg


def _cek_token(page_id, token):
    """Cek token masih valid untuk page ini."""
    import requests
    try:
        r = requests.get(f"{API}/{page_id}",
                         params={"access_token": token, "fields": "id,name"},
                         headers=H, timeout=20)
        d = r.json()
        if "error" not in d:
            info = d.get("data", d)
            return True, f"✅ Valid - {info.get('name', 'Page')}"

        err = d["error"]
        code = err.get("code")
        if code == 190:
            return False, "Token expired"
        return False, err.get("message", "")[:100]
    except Exception as e:
        return False, f"Error: {str(e)[:80]}"


def _long_lived(user_token, app_id, app_secret):
    """Tukar short-lived user token -> long-lived user token."""
    import requests
    try:
        r = requests.get(f"{API}/oauth/access_token", params={
            "grant_type": "fb_exchange_token",
            "client_id": app_id,
            "client_secret": app_secret,
            "fb_exchange_token": user_token,
        }, headers=H, timeout=20)
        d = r.json()
        if "error" in d:
            print(f"[Facebook] Long-lived gagal: {d['error'].get('message', '')[:80]}")
            return None
        return d.get("access_token")
    except Exception as e:
        print(f"[Facebook] Long-lived error: {e}")
        return None


def _exchange_page_token(user_token, page_id):
    """Tukar user token -> page access token."""
    import requests
    try:
        r = requests.get(f"{API}/me/accounts",
                         params={"access_token": user_token, "fields": "id,access_token"},
                         headers=H, timeout=20)
        d = r.json()
        if "error" in d:
            return None
        for p in d.get("data", []):
            if p["id"] == page_id:
                return p.get("access_token")
    except Exception:
        pass
    return None


def _save(page_id, token):
    """Simpan token baru ke .env."""
    from src import env_manager as env
    env.set_value("FACEBOOK_PAGE_ID", page_id)
    env.set_value("FACEBOOK_ACCESS_TOKEN", token)


def status():
    """Status token sekarang."""
    import requests
    page_id, token = _env()
    if not page_id or not token:
        return "❌ Page ID / token belum diisi"
    try:
        r = requests.get(f"{API}/{page_id}",
                         params={"access_token": token, "fields": "id,name"},
                         headers=H, timeout=20)
        d = r.json()
        if "error" in d:
            return f"❌ {d['error'].get('message', '')[:100]}"
        info = d.get("data", d)
        return f"✅ {info.get('name')} (ID: {info.get('id')})"
    except Exception as e:
        return f"❌ {str(e)[:80]}"


if __name__ == "__main__":
    print("Status:", status())
    tok, msg = get_page_token()
    print("Result:", msg)
    if tok:
        print("Token:", tok[:25], "...")
