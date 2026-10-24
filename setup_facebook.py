"""
Alat bantu dapat Page Access Token Facebook baru.

Kalau token di .env sudah expired, jalankan:
    python setup_facebook.py

Script ini memberi link login (Graph API Explorer) dan menunggu kamu
paste hasil /me/accounts. Setelah itu token otomatis disimpan ke .env
lalu dikonversi jadi long-lived page token.
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv
load_dotenv()

import requests

API = "https://graph.facebook.com/v18.0"
H = {"User-Agent": "Mozilla/5.0 (Linux; Android) autopilot-content/1.0"}


def step_1_daftar_permission():
    """Cek permission apa yang sudah dimiliki user token dari Graph Explorer."""
    print("=" * 62)
    print(" LANGKAH 1 - Buat User Token di Graph API Explorer")
    print("=" * 62)
    print()
    print("Buka: https://developers.facebook.com/tools/explorer")
    print()
    print("Pilih aplikasi kamu di dropdown kiri bawah, lalu klik")
    print("'Get Access Token' -> 'Get User Access Token'")
    print()
    print("Centang permission ini:")
    print("   [x] pages_show_list")
    print("   [x] pages_read_engagement")
    print("   [x] pages_manage_posts")
    print("   [x] pages_manage_video")
    print("   [x] publish_video")
    print("   [x] public_profile")
    print()
    print("Klik 'Generate Access Token', lalu copy token-nya.")
    print()


def step_2_cek_user_token(user_token):
    """Validasi user token & ambil daftar page."""
    print("=" * 62)
    print(" LANGKAH 2 - Cek User Token")
    print("=" * 62)
    try:
        r = requests.get(f"{API}/me", params={
            "access_token": user_token, "fields": "id,name"}, headers=H, timeout=20)
        d = r.json()
        if "error" in d:
            print("❌ Token tidak valid:")
            print("   ", d["error"].get("message", "")[:150])
            return None
        print(f"✅ Token valid untuk: {d.get('name')} (ID: {d.get('id')})")
    except Exception as e:
        print("❌ Error:", str(e)[:120])
        return None

    try:
        r = requests.get(f"{API}/me/accounts", params={
            "access_token": user_token, "fields": "id,name,access_token"},
            headers=H, timeout=20)
        d = r.json()
        if "error" in d:
            print("❌ Gagal ambil daftar page:", d["error"].get("message", "")[:120])
            return None
        pages = d.get("data", [])
        if not pages:
            print("⚠️  Tidak ada page. Pastikan kamu admin dan ada izin")
            print("   'pages_show_list' + page di bawah 'Your Pages'.")
            return None
        print("\nPage yang kamu kelola:")
        target = None
        for i, p in enumerate(pages, 1):
            print(f"   {i}. {p['name']}  (ID: {p['id']})")
        print()
        return pages
    except Exception as e:
        print("❌ Error:", str(e)[:120])
        return None


def step_3_pilih_dan_simpan(pages):
    """Pilih page, long-lived token, lalu simpan ke .env."""
    print("=" * 62)
    print(" LANGKAH 3 - Simpan Page Token")
    print("=" * 62)
    app_id = os.getenv("FACEBOOK_APP_ID", "")
    app_secret = os.getenv("FACEBOOK_APP_SECRET", "")

    default_idx = 0
    for i, p in enumerate(pages):
        if p["id"] == os.getenv("FACEBOOK_PAGE_ID", ""):
            default_idx = i

    raw = input(f"Pilih nomor page [default {default_idx + 1}]: ").strip()
    idx = (int(raw) - 1) if raw.isdigit() else default_idx
    if idx < 0 or idx >= len(pages):
        print("❌ Nomor tidak valid.")
        return False
    page = pages[idx]
    page_token = page.get("access_token")
    print(f"\nDipilih: {page['name']} (ID: {page['id']})")

    # Coba jadi long-lived (valid 60 hari, bisa di-refresh otomatis)
    if app_id and app_secret:
        try:
            r = requests.get(f"{API}/oauth/access_token", params={
                "grant_type": "fb_exchange_token",
                "client_id": app_id,
                "client_secret": app_secret,
                "fb_exchange_token": page_token,
            }, headers=H, timeout=20)
            d = r.json()
            if "error" in d:
                print(f"⚠️  Long-lived gagal: {d['error'].get('message','')[:90]}")
                print("   tetap pakai page token biasa.")
            else:
                ll = d.get("access_token")
                # tukar long-lived user token -> page token lagi
                r2 = requests.get(f"{API}/me/accounts", params={
                    "access_token": ll, "fields": "id,access_token"},
                    headers=H, timeout=20)
                d2 = r2.json()
                if "error" not in d2:
                    for p in d2.get("data", []):
                        if p["id"] == page["id"]:
                            page_token = p["access_token"]
                            break
                print("✅ Berhasil dibuat long-lived (~60 hari).")
        except Exception as e:
            print("⚠️  Long-lived error:", str(e)[:80])

    # Simpan ke .env
    try:
        from src import env_manager as env
        env.set_value("FACEBOOK_PAGE_ID", page["id"])
        env.set_value("FACEBOOK_ACCESS_TOKEN", page_token)
        print(f"\n✅ Tersimpan ke .env")
        print(f"   FACEBOOK_PAGE_ID     = {page['id']}")
        print(f"   FACEBOOK_ACCESS_TOKEN = {page_token[:20]}...{page_token[-6:]}")
        return True
    except Exception as e:
        print("❌ Gagal simpan:", str(e)[:120])
        print("   Token (simpan manual):")
        print(f"   {page_token}")
        return False


def main():
    print()
    step_1_daftar_permission()
    print("Paste User Access Token di bawah (tekan Enter kosong untuk quit):")
    user_token = input("> ").strip()
    if not user_token:
        print("Dibatalkan.")
        return
    print()
    pages = step_2_cek_user_token(user_token)
    if not pages:
        print("\nGagal. Coba ulang dengan permission yang benar.")
        return
    print()
    if step_3_pilih_dan_simpan(pages):
        print()
        from src.fb_auth import status
        print("Verifikasi:", status())


if __name__ == "__main__":
    main()
