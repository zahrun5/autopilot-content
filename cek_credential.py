"""
Cek & refresh credential upload (Facebook / YouTube / Telegram).
Jalankan: python cek_credential.py
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from dotenv import load_dotenv
load_dotenv()

from src.env_manager import get

FB_VERSION = "v18.0"


def cek_facebook():
    print("\n=== FACEBOOK ===")
    page_id = get("FACEBOOK_PAGE_ID")
    token = get("FACEBOOK_ACCESS_TOKEN")
    app_id = get("FACEBOOK_APP_ID")
    app_secret = get("FACEBOOK_APP_SECRET")

    if not page_id:
        print("❌ FACEBOOK_PAGE_ID kosong di .env")
        return False
    if not token:
        print("❌ FACEBOOK_ACCESS_TOKEN kosong di .env")
        return False

    import requests
    H = {"User-Agent": "Mozilla/5.0 (Linux; Android) autopilot-content/1.0"}

    r = requests.get(
        f"https://graph.facebook.com/{FB_VERSION}/{page_id}",
        params={"access_token": token, "fields": "id,name"},
        timeout=20, headers=H,
    )
    data = r.json()

    if "error" in data:
        err = data["error"]
        print("❌ Token bermasalah:")
        print(f"   {err.get('message')}")
        if err.get("code") == 190:
            print("\n   → Token EXPIRED.")
            if app_id and app_secret:
                print("   → APP_ID/SECRET ada, tapi refresh butuh token yang valid.")
            print("   → Perbaiki: python setup_facebook.py")
        return False

    info = data.get("data", data)
    print(f"✅ Page : {info.get('name')} (ID: {info.get('id')})")

    if app_id and app_secret:
        print("✅ APP_ID + APP_SECRET ada (auto-refresh aktif)")
    else:
        print("ℹ️  APP_ID/SECRET belum diisi → auto-refresh tidak aktif")

    # Cek scope token
    try:
        d = requests.get(
            f"https://graph.facebook.com/{FB_VERSION}/debug_token",
            params={"input_token": token, "access_token": token},
            timeout=20, headers=H,
        ).json()
        dd = d.get("data", {})
        scopes = set(dd.get("scopes", []))
        print(f"   Tipe  : {dd.get('type')}")
        print(f"   Scope : {', '.join(sorted(scopes))}")
        needed = {"pages_manage_posts"}
        if needed.issubset(scopes):
            print("   ✅ pages_manage_posts ADA (wajib untuk upload)")
            return True
        print(f"   ❌ Scope kurang: {', '.join(sorted(needed - scopes))}")
        return False
    except Exception as e:
        print(f"   (debug_token gagal: {str(e)[:60]})")
        return True


def cek_youtube():
    print("\n=== YOUTUBE ===")
    from src import yt_auth

    status = yt_auth.status()
    print(f"   {status}")

    if not yt_auth.has_token():
        print("❌ Token OAuth belum ada")
        print("   → python setup_youtube.py import   (dari project ytbot)")
        print("   → python setup_youtube.py login    (login baru)")
        return False

    from config.settings import YOUTUBE_CLIENT_SECRETS
    try:
        creds = yt_auth.load_creds(YOUTUBE_CLIENT_SECRETS, interactive=False)
        print(f"   client_id : {creds.client_id[:35]}...")
        print(f"   ✅ siap upload")
        return True
    except Exception as e:
        print(f"❌ Token tidak bisa dipakai: {str(e)[:100]}")
        print("   → python setup_youtube.py login")
        return False


def cek_telegram():
    print("\n=== TELEGRAM ===")
    tok = get("TELEGRAM_BOT_TOKEN")
    if not tok:
        print("❌ TELEGRAM_BOT_TOKEN kosong di .env")
        return False
    try:
        import requests
        r = requests.get(f"https://api.telegram.org/bot{tok}/getMe", timeout=15)
        d = r.json()
        if d.get("ok"):
            print(f"✅ Bot : @{d['result'].get('username')}")
            return True
        print(f"❌ Token ditolak: {d.get('description')}")
        return False
    except Exception as e:
        print(f"❌ Error: {str(e)[:80]}")
        return False


def cek_semua():
    print("=" * 50)
    print("  CEK CREDENTIAL UPLOAD")
    print("=" * 50)
    fb = cek_facebook()
    yt = cek_youtube()
    tg = cek_telegram()
    print("\n" + "=" * 50)
    print(f"Facebook : {'✅ siap' if fb else '❌ perlu diperbaiki'}")
    print(f"YouTube  : {'✅ siap' if yt else '❌ perlu diperbaiki'}")
    print(f"Telegram : {'✅ siap' if tg else '❌ perlu diperbaiki'}")
    print("=" * 50)
    return fb, yt, tg


if __name__ == "__main__":
    cek_semua()
