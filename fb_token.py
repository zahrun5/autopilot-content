"""
Helper Facebook Page Access Token.

Pakai:
  python fb_token.py llt       # user token -> long-lived -> page token (simpan ke .env)
  python fb_token.py scopes    # cek tipe, scope, dan masa berlaku token
  python fb_token.py list      # daftar page yang bisa diakses
  python fb_token.py refresh   # refresh page token sekarang (pakai user token)
  python fb_token.py link      # panduan cara dapat user token

Dua token terpisah di .env:
  FACEBOOK_USER_ACCESS_TOKEN  - dari Graph API Explorer (untuk refresh)
  FACEBOOK_PAGE_ACCESS_TOKEN  - turunan long-lived (dipakai upload)
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from dotenv import load_dotenv
load_dotenv()

from src import fb_auth

API = fb_auth.API

# Scope yang dibutuhkan untuk upload video ke Page
NEEDED_SCOPES = [
    "pages_show_list",
    "pages_read_engagement",
    "pages_manage_posts",
    "pages_manage_video",
    "publish_video",
    "public_profile",
]


def hdr(t=20):
    return {"User-Agent": "Mozilla/5.0 (Linux; Android) autopilot-content/1.0"}


def llt():
    """
    Alur lengkap: user token (dari Explorer) -> long-lived user token
    -> page token, disimpan ke .env.
    """
    print("=" * 62)
    print(" TUKAR KE LONG-LIVED PAGE TOKEN")
    print("=" * 62)

    user_tok = fb_auth.user_token()
    if not user_tok:
        print("❌ FACEBOOK_USER_ACCESS_TOKEN belum diisi di .env")
        print()
        print("👉 Ambil user token dari Graph API Explorer:")
        print("   https://developers.facebook.com/tools/explorer")
        print("   → Get Access Token → Get User Access Token")
        print("   → centang: " + ", ".join(NEEDED_SCOPES))
        print("   → paste ke FACEBOOK_USER_ACCESS_TOKEN di .env")
        return None

    print(f"User token : {user_tok[:30]}... (len {len(user_tok)})")
    print()

    tok, msg = fb_auth.long_lived(user_tok)
    if not tok:
        print(f"❌ {msg}")
        return None
    print(f"✅ {msg}: {tok[:25]}...")

    pid, ptok, pmsg = fb_auth.page_token_from(tok)
    if not ptok:
        print(f"❌ Gagal ambil page token: {pmsg}")
        return None

    print()
    print(f"✅ Page: {pmsg} (ID: {pid})")
    print(f"   Page token: {ptok[:25]}...")

    from src import env_manager as env
    env.set_value("FACEBOOK_PAGE_ACCESS_TOKEN", ptok)
    env.set_value("FACEBOOK_PAGE_ID", pid)
    print()
    print("✅ .env diupdate:")
    print(f"   FACEBOOK_PAGE_ID={pid}")
    print(f"   FACEBOOK_PAGE_ACCESS_TOKEN={ptok[:25]}...")
    print()
    print("Verifikasi:")
    scopes()
    return ptok


def scopes():
    """Cek tipe, scope, dan masa berlaku page token sekarang."""
    import requests

    tok = fb_auth.page_token()
    app_id, app_secret = fb_auth.app_creds()

    if not tok:
        print("❌ FACEBOOK_PAGE_ACCESS_TOKEN belum diisi di .env")
        return

    # debug_token butuh access_token yang valid -> pakai app access token
    app_token = f"{app_id}|{app_secret}" if app_secret else tok
    r = requests.get(f"{API}/debug_token", params={
        "input_token": tok, "access_token": app_token,
    }, timeout=20, headers=hdr())
    d = r.json()

    if "error" in d:
        print("❌", d["error"].get("message", "")[:150])
        print()
        print("💡 Token expired. Ambil user token baru, lalu: python fb_token.py llt")
        return

    data = d.get("data", {})
    print("=== INFO TOKEN ===")
    print(f"  Tipe    : {data.get('type')}")
    print(f"  App ID  : {data.get('app_id')}")
    print(f"  User ID : {data.get('user_id')}")
    print(f"  Valid   : {data.get('is_valid')}")

    import datetime
    exp = data.get("expires_at")
    if exp:
        print(f"  Expires : {datetime.datetime.fromtimestamp(int(exp))}")
    else:
        print("  Expires : (tidak ada) → TIDAK KEDALUWARSA ✅")

    print("\n=== SCOPE ===")
    current = set(data.get("scopes", []))
    for s in NEEDED_SCOPES:
        mark = "✅" if s in current else "❌"
        print(f"  {mark} {s}")

    missing = [s for s in NEEDED_SCOPES if s not in current]
    if missing:
        print(f"\n⚠️ Scope kurang: {', '.join(missing)}")
        print("   Perlu request ulang user token dengan scope tersebut,")
        print("   lalu jalankan ulang: python fb_token.py llt")
    else:
        print("\n✅ Semua scope lengkap!")


def list_pages():
    """Tampilkan page yang bisa diakses + token-nya."""
    user_tok = fb_auth.user_token()
    if not user_tok:
        print("❌ FACEBOOK_USER_ACCESS_TOKEN belum diisi di .env")
        return
    pid, ptok, msg = fb_auth.page_token_from(user_tok)
    if not ptok:
        print("❌", msg)
        return
    import requests
    r = requests.get(f"{API}/me/accounts", params={
        "access_token": user_tok,
        "fields": "id,name,access_token,fan_count,category",
    }, timeout=20, headers=hdr())
    for p in r.json().get("data", []):
        mark = " ← dipakai" if p["id"] == pid else ""
        print(f"  ID       : {p['id']}")
        print(f"  Nama     : {p['name']}{mark}")
        print(f"  Fans     : {p.get('fan_count', '?')}")
        print()


def refresh():
    """Refresh page token sekarang dari user token."""
    tok, msg = fb_auth.get_page_token()
    print(msg)
    if tok:
        print(f"Token: {tok[:25]}...")
    return tok


def link():
    """Panduan cara dapat user token."""
    app_id, app_secret = fb_auth.app_creds()
    print("=== CARA DAPAT USER TOKEN ===\n")
    print("Graph API Explorer:")
    print("  1. Buka https://developers.facebook.com/tools/explorer")
    print(f"  2. Pilih app: {app_id or '<APP_ID>'}")
    print("  3. Klik 'Get Access Token' → pilih 'User'")
    print("  4. Centang SEMUA permission:")
    for s in NEEDED_SCOPES:
        print(f"       ☑ {s}")
    print("  5. Generate → copy token")
    print("  6. Paste ke .env sebagai FACEBOOK_USER_ACCESS_TOKEN")
    print("  7. Jalankan: python fb_token.py llt\n")

    if not app_secret:
        print("⚠️  Untuk token long-lived, set di .env:")
        print("      FACEBOOK_APP_ID=...")
        print("      FACEBOOK_APP_SECRET=...")
        print("    (developers.facebook.com → App → Settings → Basic)")


if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else "scopes"
    {
        "llt": llt,
        "scopes": scopes,
        "list": list_pages,
        "refresh": refresh,
        "link": link,
    }.get(cmd, scopes)()
