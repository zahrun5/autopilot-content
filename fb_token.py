"""
Helper untuk setup Facebook Page Access Token.

Pakai:
  python fb_token.py list          # lihat daftar page yang kamu punya
  python fb_token.py exchange      # tukar user token -> page token (per page)
  python fb_token.py scopes        # cek permission token sekarang
"""

import os
import sys
import requests

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from dotenv import load_dotenv
load_dotenv()

API = "https://graph.facebook.com/v18.0"
TOKEN = os.getenv("FACEBOOK_ACCESS_TOKEN", "")
PAGE_ID = os.getenv("FACEBOOK_PAGE_ID", "")

# Scope yang dibutuhkan untuk upload video ke Page
NEEDED_SCOPES = [
    "pages_show_list",
    "pages_read_engagement",
    "pages_manage_posts",
    "publish_video",
    "public_profile",
]

APP_ID = os.getenv("FACEBOOK_APP_ID", "2568866483527034")
APP_SECRET = os.getenv("FACEBOOK_APP_SECRET", "")
# Harus terdaftar di "Valid OAuth Redirect URIs" di pengaturan app
REDIRECT_URI = os.getenv("FACEBOOK_REDIRECT_URI", "https://www.facebook.com/connect/auth_success")


def simpan_env(key, value, env_path=".env"):
    """Update/tambah satu baris KEY=VALUE di .env."""
    lines = open(env_path).read().splitlines() if os.path.exists(env_path) else []
    out, found = [], False
    for ln in lines:
        if ln.startswith(f"{key}="):
            out.append(f"{key}={value}")
            found = True
        else:
            out.append(ln)
    if not found:
        out.append(f"{key}={value}")
    open(env_path, "w").write("\n".join(out) + "\n")


def get_long_lived(user_token):
    """Tukar short-lived user token -> long-lived (60 hari). Butuh APP_SECRET."""
    if not APP_SECRET:
        print("❌ FACEBOOK_APP_SECRET belum di-set di .env")
        print("   Ambil dari: developers.facebook.com → App → Settings → Basic")
        return None

    # Step 1: tukar ke long-lived user token
    r = requests.get(f"{API}/oauth/access_token", params={
        "grant_type": "fb_exchange_token",
        "client_id": APP_ID,
        "client_secret": APP_SECRET,
        "fb_exchange_token": user_token,
    }, timeout=20, headers=hdr())
    d = r.json()
    if "error" in d:
        print("❌ Long-lived exchange gagal:", d["error"].get("message"))
        return None

    llt = d.get("access_token")
    print(f"✅ Long-lived user token: {llt[:25]}...")

    # Step 2: tukar ke page token (per page)
    print("\n=== TUKAR KE PAGE TOKEN ===")
    for p in list_pages_data(llt):
        print(f"\n  ID   : {p['id']}")
        print(f"  Nama : {p['name']}")
        print(f"  Fans : {p.get('fan_count','?')}")

        pr = requests.get(f"{API}/{p['id']}", params={
            "access_token": llt, "fields": "id,name,access_token",
        }, timeout=20, headers=hdr())
        pd = pr.json()
        if "error" in pd:
            print(f"  ❌ {pd['error'].get('message')[:120]}")
            continue

        pt = pd.get("access_token")
        if pt:
            print(f"  ✅ Page token: {pt[:25]}...")
            print(f"  📝 Copy ke .env:")
            print(f"       FACEBOOK_PAGE_ID={p['id']}")
            print(f"       FACEBOOK_ACCESS_TOKEN={pt}")
            if not PAGE_ID or p['id'] == PAGE_ID:
                simpan_env("FACEBOOK_PAGE_ID", p['id'])
                simpan_env("FACEBOOK_ACCESS_TOKEN", pt)
                print("  ✅ .env sudah diupdate otomatis")

    return llt


def list_pages_data(tok=None):
    """Return list page (data saja)."""
    t = tok or TOKEN
    r = requests.get(f"{API}/me/accounts", params={
        "access_token": t, "fields": "id,name,access_token,fan_count",
    }, timeout=20, headers=hdr())
    d = r.json()
    if "error" in d:
        return []
    return d.get("data", [])


def oauth_url():
    """URL OAuth untuk request token dengan scope lengkap di luar Explorer."""
    scopes = ",".join(NEEDED_SCOPES)
    return (
        f"https://www.facebook.com/v18.0/dialog/oauth"
        f"?client_id={APP_ID}"
        f"&redirect_uri={REDIRECT_URI}"
        f"&scope={scopes}"
        f"&response_type=token"
    )


def hdr(t=20):
    return {"User-Agent": "Mozilla/5.0 (Linux; Android) autopilot-content/1.0"}


def list_pages():
    """Tampilkan semua page yang bisa diakses user token."""
    r = requests.get(f"{API}/me/accounts", params={
        "access_token": TOKEN,
        "fields": "id,name,access_token,fan_count,category",
    }, timeout=20, headers=hdr())
    data = r.json()

    if "error" in data:
        print("❌ Error:", data["error"].get("message"))
        print("\nToken yang di .env mungkin tidak valid / expired.")
        return

    print("=== PAGE YANG BISA DIAKSES ===")
    for p in data.get("data", []):
        exp = p.get("access_token")
        exp_txt = "tidak ada"
        if exp:
            import datetime
            dt = datetime.datetime.fromtimestamp(int(exp))
            exp_txt = dt.strftime("%Y-%m-%d %H:%M")
        print(f"\n  ID       : {p['id']}")
        print(f"  Nama     : {p['name']}")
        print(f"  Fans     : {p.get('fan_count','?')}")
        print(f"  Expires  : {exp_txt}")
        print(f"  -> set ke .env : FACEBOOK_PAGE_ID={p['id']}")


def get_page_token(page_id):
    """Tukar user token jadi page access token."""
    r = requests.get(f"{API}/{page_id}", params={
        "access_token": TOKEN,
        "fields": "id,name,access_token",
    }, timeout=20, headers=hdr())
    data = r.json()

    if "error" in data:
        err = data["error"]
        print(f"❌ {err.get('message')}")
        print(f"   code={err.get('code')} subcode={err.get('error_subcode')}")
        return None

    return data


def exchange():
    """Tukar user token -> page token dan simpan ke .env."""
    pid = sys.argv[2] if len(sys.argv) > 2 else PAGE_ID
    if not pid:
        print("❌ FACEBOOK_PAGE_ID kosong. Jalankan: python fb_token.py list")
        return

    print(f"🔄 Menukar token untuk page {pid}...")
    data = get_page_token(pid)

    if not data:
        print("\n💡 Penyebab & solusi:")
        print("   Token kamu saat ini hanya punya scope 'pages_show_list'.")
        print("   Untuk upload video butuh tambahan scope. Cara dapat:")
        print("   1. Buka https://developers.facebook.com/tools/explorer")
        print("   2. Pilih app 'aibot-uploader' (atau app kamu)")
        print("   3. Tab 'User' → 'Settings' → centang:")
        for s in NEEDED_SCOPES:
            print(f"        - {s}")
        print("   4. Klik 'Get Access Token'")
        print("   5. Update OPENROUTER... eh, FACEBOOK_ACCESS_TOKEN di .env")
        print("   6. Jalankan ulang: python fb_token.py exchange")
        return

    print(f"✅ Page  : {data.get('name')}")
    pt = data.get("access_token")
    if pt:
        simpan_env("FACEBOOK_ACCESS_TOKEN", pt)
        print("   Page token disimpan ke .env")
    else:
        print("   ⚠️ Tidak ada page token di respons (token user kurang izin?)")

    # Simpan ke .env
    env_path = ".env"
    if os.path.exists(env_path):
        lines = open(env_path).read().splitlines()
        out = []
        for ln in lines:
            if ln.startswith("FACEBOOK_PAGE_ID="):
                out.append(f"FACEBOOK_PAGE_ID={pid}")
            else:
                out.append(ln)
        open(env_path, "w").write("\n".join(out) + "\n")
        print(f"\n✅ .env diupdate: FACEBOOK_PAGE_ID={pid}")


def scopes():
    """Cek permission/expire dari token sekarang."""
    r = requests.get(f"{API}/debug_token", params={
        "input_token": TOKEN, "access_token": TOKEN,
    }, timeout=20, headers=hdr())
    d = r.json()

    if "error" in d:
        print("❌", d["error"].get("message"))
        return

    data = d.get("data", {})
    print("=== INFO TOKEN ===")
    print(f"  Tipe    : {data.get('type')}")
    print(f"  App ID  : {data.get('app_id')}")
    print(f"  User ID : {data.get('user_id')}")
    print(f"  Valid   : {data.get('is_valid')}")

    import datetime
    for key, label in [("expires_at", "Expires"), ("data_access_expires_at", "Data akses")]:
        ts = data.get(key)
        if ts:
            print(f"  {label:10}: {datetime.datetime.fromtimestamp(int(ts))}")

    print("\n=== SCOPE ===")
    current = set(data.get("scopes", []))
    for s in NEEDED_SCOPES:
        mark = "✅" if s in current else "❌"
        print(f"  {mark} {s}")

    missing = [s for s in NEEDED_SCOPES if s not in current]
    if missing:
        print(f"\n⚠️ Scope kurang: {', '.join(missing)}")
        print("   Perlu request ulang token dengan scope tersebut.")
    else:
        print("\n✅ Semua scope lengkap!")


def link():
    """Print link untuk dapat token dengan scope lengkap."""
    print("=== CARA DAPAT TOKEN DENGAN SCOPE LENGKAP ===\n")
    print("Opsi 1 (paling gampang) — Graph API Explorer:")
    print("  1. Buka https://developers.facebook.com/tools/explorer")
    print(f"  2. Pilih app: {APP_ID}")
    print("  3. Klik 'Get Token' → pilih 'User'")
    print("  4. Centang SEMUA permission:")
    for s in NEEDED_SCOPES:
        print(f"       ☑ {s}")
    print("  5. Copy token → paste ke .env (FACEBOOK_ACCESS_TOKEN)\n")

    print("Opsi 2 — link OAuth (pakai ini kalau Explorer bingung):\n")
    print(oauth_url())
    print("\n  ⚠️  Kalau muncul error 'Domain dari URL ini tidak termasuk dalam")
    print("      domain aplikasi ini', maka:")
    print("      1. Buka https://developers.facebook.com/apps/"
          f"{APP_ID}/settings/basic/")
    print("      2. 'Valid OAuth Redirect URIs' → tambahkan:")
    print(f"           {REDIRECT_URI}")
    print("      3. Save, lalu buka link di atas lagi\n")
    print("  -> Setelah authorize, copy access_token dari address bar\n")

    if not APP_SECRET:
        print("⚠️  Untuk token long-lived (60 hari), set di .env:")
        print("      FACEBOOK_APP_ID=...")
        print("      FACEBOOK_APP_SECRET=...")
        print("    (dari developers.facebook.com → App → Settings → Basic)")


if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else "list"
    {
        "list": list_pages,
        "exchange": exchange,
        "scopes": scopes,
        "link": link,
        "llt": lambda: get_long_lived(TOKEN),
    }.get(cmd, list_pages)()
