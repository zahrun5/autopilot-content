"""
Upload Module - Upload video ke YouTube dan Facebook
Gratis via official API
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from config.settings import (
    YOUTUBE_CLIENT_SECRETS,
    FACEBOOK_PAGE_ID,
    FACEBOOK_ACCESS_TOKEN,
)

# ============================================================
# YOUTUBE UPLOAD
# ============================================================

def _login_youtube_interactive(scopes, client_secrets_path):
    """
    Login YouTube via loopback server.

    Catatan: OOB flow (urn:ietf:wg:oauth:2.0:oob) sudah di-deprecate Google
    (error 400 redirect_uri_mismatch). Jadi kita jalankan server lokal
    di HP, lalu user buka link auth di browser HP yang sama
    (localhost = HP itu sendiri, jadi redirect intercepted dengan benar).

    Fallback: kalau browser tidak bisa buka localhost, user boleh paste
    kode / URL redirect secara manual.
    """
    from google_auth_oauthlib.flow import InstalledAppFlow
    import socket
    import threading
    import urllib.parse

    def free_port():
        s = socket.socket()
        s.bind(("127.0.0.1", 0))
        p = s.getsockname()[1]
        s.close()
        return p

    port = free_port()
    flow = InstalledAppFlow.from_client_secrets_file(client_secrets_path, scopes=scopes)

    # Jangan set redirect_uri di authorization_url - run_local_server
    # akan menetapkannya sendiri ke http://localhost:{port}
    auth_url, _ = flow.authorization_url(
        access_type="offline",   # simpan refresh_token
        prompt="consent",
    )

    print("\n" + "=" * 62)
    print("  LOGIN YOUTUBE - BUKA LINK INI DI BROWSER HP")
    print("=" * 62)
    print(auth_url)
    print("=" * 62)
    print("Setelah klik Authorize, OLEH OTOMATIS (tidak perlu copy kode).")
    print(f"Server lokal aktif di port {port}.")
    print()
    print("⚠️  Kalau halaman browser ERROR / tidak Redirect:")
    print("   - Pastikan buka link di browser HP yang sama (bukan PC)")
    print("   - Atau paste KODE / URL redirect manual di bawah")
    print("-" * 62)

    # Server lokal di thread terpisah supaya bisa di-cancel manual
    result = {}

    def run_server():
        try:
            result["creds"] = flow.run_local_server(
                port=port, open_browser=False,
                authorization_prompt_message="", success_message="✅ Login berhasil! Kembali ke Termux.",
            )
        except Exception as e:
            result["error"] = e

    t = threading.Thread(target=run_server, daemon=True)
    t.start()

    # Tunggu callback dari browser, atau user paste manual
    while t.is_alive():
        t.join(timeout=1)

    if "creds" in result:
        print("\n✅ Token diperoleh!")
        return result["creds"]

    # Fallback: coba dari input manual
    print("\n⚠️  Server selesai tanpa capture token otomatis.")
    print("Paste KODE verifikasi, atau paste URL lengkap yang muncul di browser:")
    manual = input("Input: ").strip()
    if not manual:
        raise RuntimeError("Login dibatalkan.")

    if "code=" in manual:
        # parse dari URL
        qs = urllib.parse.urlparse(manual).query or manual.split("?", 1)[-1]
        params = urllib.parse.parse_qs(qs)
        code = params.get("code", [None])[0]
    else:
        code = manual.split(" ")[-1]

    if not code:
        raise RuntimeError("Kode tidak terbaca dari input.")

    flow.fetch_token(code=code)
    print("\n✅ Token diperoleh (manual)!")
    return flow.credentials


def upload_youtube(video_path: str, judul: str, deskripsi: str, tags: list) -> str:
    """
    Upload video ke YouTube via YouTube Data API v3.
    
    Setup awal (sekali saja):
    1. Buat project di Google Cloud Console
    2. Enable YouTube Data API v3
    3. Buat OAuth 2.0 credentials (Desktop app)
    4. Download client_secrets.json → simpan di config/yt_client_secrets.json
    5. pip install google-auth google-auth-oauthlib google-api-python-client
    
    Returns: YouTube video URL
    """
    try:
        from google_auth_oauthlib.flow import InstalledAppFlow
        from googleapiclient.discovery import build
        from googleapiclient.http import MediaFileUpload
        from google.oauth2.credentials import Credentials
        import pickle
    except ImportError:
        raise ImportError(
            "Jalankan: pip install google-auth google-auth-oauthlib google-api-python-client"
        )

    SCOPES = ["https://www.googleapis.com/auth/youtube.upload"]
    TOKEN_FILE = "config/yt_token.pickle"

    # Load atau minta auth
    creds = None
    if os.path.exists(TOKEN_FILE):
        with open(TOKEN_FILE, "rb") as f:
            creds = pickle.load(f)

    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            from google.auth.transport.requests import Request
            creds.refresh(Request())
        else:
            creds = _login_youtube_interactive(SCOPES, YOUTUBE_CLIENT_SECRETS)

        os.makedirs(os.path.dirname(TOKEN_FILE), exist_ok=True)
        with open(TOKEN_FILE, "wb") as f:
            pickle.dump(creds, f)
        print("[YouTube] Token OAuth disimpan, tidak perlu login lagi.")

    youtube = build("youtube", "v3", credentials=creds, cache_discovery=False)

    body = {
        "snippet": {
            "title": judul,
            "description": deskripsi,
            "tags": tags,
            "categoryId": "22",  # People & Blogs
            "defaultLanguage": "id",
        },
        "status": {
            "privacyStatus": "public",
            "selfDeclaredMadeForKids": False,
        },
    }

    media = MediaFileUpload(video_path, chunksize=-1, resumable=True)

    print(f"[YouTube] Uploading: '{judul}'...")
    request = youtube.videos().insert(part="snippet,status", body=body, media_body=media)

    response = None
    while response is None:
        status, response = request.next_chunk()
        if status:
            pct = int(status.progress() * 100)
            print(f"[YouTube] Upload progress: {pct}%")

    video_id = response["id"]
    url = f"https://www.youtube.com/watch?v={video_id}"
    print(f"[YouTube] Upload selesai! URL: {url}")
    return url


# ============================================================
# FACEBOOK UPLOAD
# ============================================================

def upload_facebook(video_path: str, judul: str, deskripsi: str) -> str:
    """
    Upload video ke Facebook Page via Graph API.
    
    Setup awal:
    1. Buka https://developers.facebook.com → buat app
    2. Tambahkan "Pages" permission
    3. Generate Page Access Token (tidak expire jika long-lived)
    4. Isi FACEBOOK_PAGE_ID dan FACEBOOK_ACCESS_TOKEN di config/settings.py
    5. pip install requests
    
    Returns: Facebook video URL
    """
    import requests

    if not FACEBOOK_PAGE_ID or FACEBOOK_PAGE_ID == "your_fb_page_id":
        raise ValueError("Isi FACEBOOK_PAGE_ID di config/settings.py!")
    if not FACEBOOK_ACCESS_TOKEN or FACEBOOK_ACCESS_TOKEN == "your_fb_page_access_token":
        raise ValueError("Isi FACEBOOK_ACCESS_TOKEN di config/settings.py!")

    upload_url = f"https://graph.facebook.com/v18.0/{FACEBOOK_PAGE_ID}/videos"

    print(f"[Facebook] Uploading: '{judul}'...")

    with open(video_path, "rb") as video_file:
        response = requests.post(
            upload_url,
            data={
                "title": judul,
                "description": deskripsi,
                "access_token": FACEBOOK_ACCESS_TOKEN,
            },
            files={"source": video_file},
            timeout=300,
        )

    # Baca body dulu supaya pesan error asli dari Facebook kelihatan
    # (raise_for_status() di awal menyembunyikan penyebab sebenarnya)
    try:
        data = response.json()
    except ValueError:
        response.raise_for_status()
        raise RuntimeError(f"Response FB bukan JSON: {response.text[:200]}")

    if "error" in data:
        err = data["error"]
        raise RuntimeError(
            f"FB API error: {err.get('message')} "
            f"(code={err.get('code')}, subcode={err.get('error_subcode')})"
        )

    video_id = data.get("id")
    if not video_id:
        raise RuntimeError(f"Response FB tidak punya video id: {str(data)[:200]}")

    url = f"https://www.facebook.com/{FACEBOOK_PAGE_ID}/videos/{video_id}"
    print(f"[Facebook] Upload selesai! URL: {url}")
    return url


def upload_semua(video_path: str, script: dict, force: bool = False) -> dict:
    """
    Upload ke YouTube dan Facebook sekaligus.

    Returns dict berisi URL dari tiap platform, plus 'errors' dict.
    """
    hasil = {"youtube": None, "facebook": None, "errors": {}}

    # YouTube
    if not os.path.exists(YOUTUBE_CLIENT_SECRETS):
        hasil["errors"]["youtube"] = (
            f"File {YOUTUBE_CLIENT_SECRETS} belum ada. "
            "Download OAuth client dari Google Cloud Console."
        )
        print(f"[YouTube] SKIP: {hasil['errors']['youtube']}")
    else:
        try:
            yt_url = upload_youtube(
                video_path=video_path,
                judul=script["judul"],
                deskripsi=script["deskripsi"],
                tags=script["tags"],
            )
            hasil["youtube"] = yt_url
        except Exception as e:
            print(f"[YouTube] GAGAL upload: {e}")
            hasil["errors"]["youtube"] = str(e)[:300]

    # Facebook
    if not FACEBOOK_PAGE_ID or FACEBOOK_PAGE_ID == "your_fb_page_id":
        hasil["errors"]["facebook"] = "FACEBOOK_PAGE_ID belum diisi di .env"
        print(f"[Facebook] SKIP: {hasil['errors']['facebook']}")
    elif not FACEBOOK_ACCESS_TOKEN or FACEBOOK_ACCESS_TOKEN == "your_fb_page_access_token":
        hasil["errors"]["facebook"] = "FACEBOOK_ACCESS_TOKEN belum diisi di .env"
        print(f"[Facebook] SKIP: {hasil['errors']['facebook']}")
    else:
        try:
            fb_url = upload_facebook(
                video_path=video_path,
                judul=script["judul"],
                deskripsi=script["deskripsi"],
            )
            hasil["facebook"] = fb_url
        except Exception as e:
            print(f"[Facebook] GAGAL upload: {e}")
            hasil["errors"]["facebook"] = str(e)[:300]

    return hasil


if __name__ == "__main__":
    print("Upload module siap. Jalankan via main.py")
