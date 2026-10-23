"""
Cek & refresh credential upload (Facebook / YouTube).
Jalankan: python cek_credential.py
"""

import os
import sys
import requests

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from config.settings import (
    FACEBOOK_PAGE_ID, FACEBOOK_ACCESS_TOKEN, YOUTUBE_CLIENT_SECRETS
)

FB_VERSION = "v18.0"


def cek_facebook():
    print("\n=== FACEBOOK ===")
    if not FACEBOOK_PAGE_ID:
        print("❌ FACEBOOK_PAGE_ID kosong di .env")
        return False
    if not FACEBOOK_ACCESS_TOKEN:
        print("❌ FACEBOOK_ACCESS_TOKEN kosong di .env")
        return False

    r = requests.get(
        f"https://graph.facebook.com/{FB_VERSION}/{FACEBOOK_PAGE_ID}",
        params={
            "access_token": FACEBOOK_ACCESS_TOKEN,
            "fields": "id,name",
        },
        timeout=20,
        headers={"User-Agent": "Mozilla/5.0"},
    )
    data = r.json()

    if "error" in data:
        err = data["error"]
        print(f"❌ Token bermasalah:")
        print(f"   {err.get('message')}")
        if err.get("code") == 190:
            print("\n   → Token EXPIRED. Generate ulang:")
            print("     1. https://developers.facebook.com/tools/explorer")
            print("     2. Get Token → User → centang pages_manage_posts")
            print("     3. Update FACEBOOK_ACCESS_TOKEN di .env")
        return False

    info = data.get("data", data)
    print(f"✅ Page : {info.get('name')} (ID: {info.get('id')})")

    # Cek tipe & scope token
    d = requests.get(
        f"https://graph.facebook.com/{FB_VERSION}/debug_token",
        params={"input_token": FACEBOOK_ACCESS_TOKEN, "access_token": FACEBOOK_ACCESS_TOKEN},
        timeout=20,
        headers={"User-Agent": "Mozilla/5.0"},
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


def cek_youtube():
    print("\n=== YOUTUBE ===")
    if not os.path.exists(YOUTUBE_CLIENT_SECRETS):
        print(f"❌ File {YOUTUBE_CLIENT_SECRETS} belum ada")
        print("\n   Cara setup:")
        print("   1. https://console.cloud.google.com → buat project")
        print("   2. Enable 'YouTube Data API v3'")
        print("   3. Credentials → OAuth 2.0 Client ID → Desktop app")
        print(f"   4. Download JSON → simpan sebagai {YOUTUBE_CLIENT_SECRETS}")
        return False

    print(f"✅ File {YOUTUBE_CLIENT_SECRETS} ada")
    token_file = "config/yt_token.pickle"
    if os.path.exists(token_file):
        print(f"✅ Token OAuth tersimpan ({token_file})")
        return True
    print("ℹ️  Token OAuth belum ada — akan diminta login saat upload pertama")
    return True


def cek_semua():
    print("=" * 50)
    print("  CEK CREDENTIAL UPLOAD")
    print("=" * 50)
    fb = cek_facebook()
    yt = cek_youtube()
    print("\n" + "=" * 50)
    print(f"Facebook : {'✅ siap' if fb else '❌ perlu diperbaiki'}")
    print(f"YouTube  : {'✅ siap' if yt else '❌ perlu diperbaiki'}")
    print("=" * 50)
    return fb, yt


if __name__ == "__main__":
    cek_semua()
