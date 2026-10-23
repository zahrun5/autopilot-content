"""
Test validasi pesan bot - memastikan semua pesan bisa di-parse Telegram.

Pakai: python test_pesan.py
"""

import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))


def cek_nama(nama, teks):
    """Cek apakah pesan Telegram valid (tidak akan error parse entities)."""
    errors = []

    # 1. Backtick tidak boleh berisi backslash
    for m in re.finditer(r"`([^`]*)`", teks):
        if "\\" in m.group(1):
            errors.append(f"backtick berisi escape: `{m.group(1)[:40]}`")

    # 2. Backtick harus balance
    if teks.count("`") % 2 != 0:
        errors.append("jumlah backtick tidak genap")

    # 3. Tanda * harus balance (untuk bold/italic)
    star_count = 0
    for line in teks.split("\n"):
        star_count += line.count("*")
    if star_count % 2 != 0:
        errors.append(f"tanda * tidak genap ({star_count})")

    # 4. Kurung kurawal harus balance
    if teks.count("(") != teks.count(")"):
        errors.append("kurung ( ) tidak balance")

    # 5. Kurung siku harus balance
    if teks.count("[") != texts_bracket(teks):
        errors.append("kurung [ ] tidak balance")

    if errors:
        print(f"❌ {nama}")
        for e in errors:
            print(f"   - {e}")
        return False
    print(f"✅ {nama}")
    return True


def texts_bracket(t):
    return t.count("]")


def main():
    from src.bot import (
        settings_summary_text, status_text, auto_status_text,
        kb_main, kb_settings, kb_auto, help_cmd, md, code,
    )
    from src import env_manager as env
    import asyncio

    ok = True
    print("=" * 50)
    print("  VALIDASI PESAN BOT")
    print("=" * 50)

    # Pesan statis
    msgs = {
        "settings_summary": settings_summary_text(),
        "status_text": status_text(),
        "auto_status": auto_status_text(),
    }

    # Pesan dengan nilai bermasalah (underscore, asterisk, backtick)
    nasties = [
        "config/yt_client_secrets.json",
        "sk-or-v1-abc*def_ghi`jkl",
        "https://example.com/path?a=1&b=2_x",
        "normal_value",
    ]
    for i, n in enumerate(nasties):
        msgs[f"nasty_{i}"] = f"Nilai: {code(n)}\nItalic: _{md(n)}_"

    for name, t in msgs.items():
        ok &= cek_nama(name, t)

    # Async messages
    async def test_async():
        nonlocal ok
        from telegram import Update, Message, Chat
        from src.bot import help_cmd, topik_cmd, upload_cmd

        class FakeMsg:
            text = "/help"
            chat = type("C", (), {"id": 123})()

            async def reply_text(self, *a, **k):
                return None

        class FakeUpdate:
            message = FakeMsg()

        for cmd, name in [(help_cmd, "help_cmd"), (topik_cmd, "topik_cmd"), (upload_cmd, "upload_cmd")]:
            try:
                await cmd(FakeUpdate(), None)
                print(f"✅ {name}")
            except Exception as e:
                print(f"❌ {name}: {e}")
                ok = False

    asyncio.run(test_async())

    print("=" * 50)
    print("✅ SEMUA OK" if ok else "❌ ADA MASALAH")
    print("=" * 50)
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
