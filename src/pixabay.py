"""
Pixabay Module - Fetch foto gratis berdasarkan keyword
Gratis, 100 req/jam, tidak perlu approval
"""

import os
import sys
import requests
import random

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from config.settings import PIXABAY_API_KEY, IMAGE_DIR

PIXABAY_API_URL = "https://pixabay.com/api/"


def fetch_foto(keyword: str, slide_index: int, per_page: int = 10) -> str:
    """
    Cari dan download foto dari Pixabay berdasarkan keyword.

    Returns: path file foto yang sudah didownload
    """
    os.makedirs(IMAGE_DIR, exist_ok=True)

    params = {
        "key": PIXABAY_API_KEY,
        "q": keyword,
        "image_type": "photo",
        "orientation": "horizontal",
        "per_page": per_page,
        "safesearch": "true",
        "order": "popular",
    }

    print(f"[Pixabay] Mencari foto untuk keyword: '{keyword}'...")

    response = requests.get(PIXABAY_API_URL, params=params, timeout=15)
    response.raise_for_status()

    data = response.json()
    hits = data.get("hits", [])

    if not hits:
        raise ValueError(f"Tidak ada foto ditemukan untuk keyword: '{keyword}'")

    # Pilih foto secara random agar tidak monoton
    foto = random.choice(hits)

    # Ambil URL resolusi terbaik
    foto_url = (
        foto.get("largeImageURL")
        or foto.get("webformatURL")
    )

    # Download foto
    output_path = os.path.join(IMAGE_DIR, f"slide_{slide_index:02d}.jpg")
    print(f"[Pixabay] Downloading foto: {foto_url[:60]}...")

    img_response = requests.get(foto_url, timeout=30)
    img_response.raise_for_status()

    with open(output_path, "wb") as f:
        f.write(img_response.content)

    print(f"[Pixabay] Foto disimpan: {output_path}")
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
            print(f"[Pixabay] Gagal fetch foto slide {i+1}: {e}. Coba fallback keyword...")
            try:
                path = fetch_foto("abstract background", slide_index=i)
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
