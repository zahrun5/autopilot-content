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
            flow = InstalledAppFlow.from_client_secrets_file(YOUTUBE_CLIENT_SECRETS, SCOPES)
            creds = flow.run_local_server(port=0)

        with open(TOKEN_FILE, "wb") as f:
            pickle.dump(creds, f)

    youtube = build("youtube", "v3", credentials=creds)

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
