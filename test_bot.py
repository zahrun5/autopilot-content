"""
Test bot Telegram tanpa harus buka HP.
Simulasi pesan user via Telegram Bot API.
Pakai: python test_bot.py start
"""

import os
import sys
import time
import requests

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from dotenv import load_dotenv
load_dotenv()

TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")
API = f"https://api.telegram.org/bot{TOKEN}"
H = {"User-Agent": "Mozilla/5.0"}


def get_me():
    return requests.get(f"{API}/getMe", headers=H, timeout=20).json()


def get_updates():
    r = requests.get(f"{API}/getUpdates", params={"limit": 20, "timeout": 0},
                     headers=H, timeout=25).json()
    return r.get("result", [])


def main():
    print("=" * 55)
    me = get_me()
    if not me.get("ok"):
        print("❌ Token tidak valid:", me)
        return
    print(f"Bot : @{me['result']['username']}")

    upd = get_updates()
    if not upd:
        print("\n📭 Belum ada pesan masuk.")
        print("   Buka Telegram → chat bot → kirim /start")
        print("   Lalu jalankan script ini lagi.")
        return

    print(f"\n📬 {len(upd)} pesan:")
    for u in upd:
        m = u.get("message") or (u.get("callback_query") or {}).get("message") or {}
        who = m.get("from", {}).get("first_name", "?")
        cid = m.get("chat", {}).get("id")
        text = m.get("text") or (u.get("callback_query", {}).get("data", ""))
        print(f"\n  [{who}] chat_id={cid}")
        print(f"  text: {text}")

        if m:
            print(f"  -> kirim /start ke chat {cid} untuk tampilkan menu")


if __name__ == "__main__":
    main()
