"""
Pexels Module - Fetch foto gratis berdasarkan keyword
"""

import os
import sys
import requests
import random

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from config.settings import PEXELS_API_KEY, IMAGE_DIR, VIDEO_WIDTH, VIDEO_HEIGHT

PEXELS_API_URL = "https://api.pexels.com/v1/search"


def fetch_foto(keyword: str, slide_index: int, per_page: int = 10) -> str:
    """
    Cari dan download foto dari Pexels berdasarkan keyword.
    
    Returns: path file foto yang sudah didownload
    """
    os.makedirs(IMAGE_DIR, exist_ok=True)

    headers = {"Authorization": PEXELS_API_KEY}
    params = {
        "query": keyword,
        "per_page": per_page,
        "orientation": "landscape",
        "size": "large",
    }

    print(f"[Pexels] Mencari foto untuk keyword: '{keyword}'...")

    response = requests.get(PEXELS_API_URL, headers=headers, params=params, timeout=15)
    response.raise_for_status()

    data = response.json()
    photos = data.get("photos", [])

    if not photos:
        raise ValueError(f"Tidak ada foto ditemukan untuk keyword: '{keyword}'")

    # Pilih foto secara random agar tidak monoton
    foto = random.choice(photos)

    # Ambil URL resolusi terbaik yang tersedia
    foto_url = (
        foto["src"].get("large2x")
        or foto["src"].get("large")
        or foto["src"].get("original")
    )

    # Download foto
    output_path = os.path.join(IMAGE_DIR, f"slide_{slide_index:02d}.jpg")
    print(f"[Pexels] Downloading foto: {foto_url[:60]}...")

    img_response = requests.get(foto_url, timeout=30)
    img_response.raise_for_status()

    with open(output_path, "wb") as f:
        f.write(img_response.content)

    print(f"[Pexels] Foto disimpan: {output_path}")
    return output_path


def fetch_semua_foto(slides: list) -> list:
    """
    Download foto untuk semua slide.
    
    Args:
        slides: list slide dari LLM output (tiap slide punya 'keyword_foto')
    
    Returns:
        list path foto, sesuai urutan slides
    """
    foto_paths = []
    for i, slide in enumerate(slides):
        keyword = slide.get("keyword_foto", "nature")
        try:
            path = fetch_foto(keyword, slide_index=i)
        except Exception as e:
            print(f"[Pexels] Gagal fetch foto slide {i+1}: {e}. Coba fallback keyword...")
            try:
                path = fetch_foto("background abstract", slide_index=i)
            except Exception as e2:
                raise RuntimeError(f"Foto fallback juga gagal: {e2}")
        foto_paths.append(path)
    return foto_paths


if __name__ == "__main__":
    # Test
    test_slides = [
        {"keyword_foto": "technology future"},
        {"keyword_foto": "people smiling"},
        {"keyword_foto": "nature mountain"},
    ]
    paths = fetch_semua_foto(test_slides)
    for p in paths:
        print(p)
