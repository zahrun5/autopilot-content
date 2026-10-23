"""
Test semua tombol bot secara simulasi (tanpa HP).
Mensimulasikan callback_query untuk setiap tombol dan cek tidak error.

Pakai: python test_tombol.py
"""

import asyncio
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))


class FakeQuery:
    """Pura-pura CallbackQuery."""

    def __init__(self, data):
        self.data = data
        self.edited = []
        self.answered = []
        self.errors = []

        class Msg:
            chat = type("C", (), {"id": 999})()
            message = type("M", (), {"chat_id": 999})()
        self.message = Msg()

    async def answer(self, text=None, show_alert=False):
        self.answered.append((text, show_alert))

    async def edit_message_text(self, text, reply_markup=None, parse_mode=None):
        # Validasi format Telegram seperti bot sungguhan
        if parse_mode is not None and parse_mode == "Markdown":
            _validasi_markdown(text)
        self.edited.append((text, reply_markup))


def _validasi_markdown(text):
    """Deteksi pesan yang akan ditolak Telegram (parse entities)."""
    if text.count("`") % 2 != 0:
        raise ValueError(f"Can't parse entities: backtick tidak genap -> {text[:80]!r}")
    if text.count("*") % 2 != 0:
        raise ValueError(f"Can't parse entities: tanda * tidak genap -> {text[:80]!r}")
    # backslash di dalam code span
    inside = False
    for ch in text:
        if ch == "`":
            inside = not inside
    # cek label ber-underscore di luar code span
    masked = []
    inside = False
    for ch in text:
        if ch == "`":
            inside = not inside
            masked.append("`")
        else:
            masked.append(" " if inside else ch)
    masked = "".join(masked)
    for i, line in enumerate(masked.split("\n")):
        if line.count("_") % 2 != 0:
            raise ValueError(
                f"Can't parse entities: underscore tidak genap di baris {i} -> {line[:80]!r}"
            )


async def main():
    from src.bot import button_handler, kb_main, kb_settings, kb_auto

    # ── PROTEKSI: backup .env & state scheduler, restore setelah test ──
    import shutil
    from src import env_manager as env
    from src import scheduler as sched

    env_backup = None
    if os.path.exists(env.ENV_PATH):
        env_backup = env.ENV_PATH + ".testbak"
        shutil.copy2(env.ENV_PATH, env_backup)
    sched_backup = sched.get_state()

    print("=" * 55)
    print("  TEST SEMUA TOMBOL BOT")
    print("=" * 55)

    # Kumpulkan semua callback_data dari semua keyboard
    buttons = []

    def collect(kb, label):
        for row in kb.inline_keyboard:
            for btn in row:
                buttons.append((label, btn.callback_data))

    collect(kb_main(), "main")
    collect(kb_settings("all"), "settings/all")
    collect(kb_settings("llm"), "settings/llm")
    collect(kb_settings("media"), "settings/media")
    collect(kb_settings("sosial"), "settings/sosial")
    collect(kb_auto(), "auto")

    # Callback data tambahan
    # CATATAN: jangan sertakan action destructive (settings_reset_yes)
    # karena test ini akan benar-benar menghapus credential dari .env!
    buttons += [
        ("extra", "back_main"),
    ]

    class FakeContext:
        bot = None
    ok = True
    seen = set()
    for label, data in buttons:
        if data in seen:
            continue
        seen.add(data)
        query = FakeQuery(data)
        try:
            await button_handler(type("U", (), {"callback_query": query})(), FakeContext())
            status = "✅"
        except Exception as e:
            status = f"❌ {e}"
            ok = False
        print(f"  {status} {label:16} {data}")

    print("=" * 55)
    print(f"✅ SEMUA {len(seen)} TOMBOL OK" if ok else "❌ ADA TOMBOL BERMASALAH")
    print("=" * 55)

    # ── Test wrapper fallback dengan pesan markdown rusak ──
    print("\n[TEST] Fallback pesan markdown rusak:")

    class BrokenQuery:
        """Simulasi Telegram yang reject pesan markdown rusak."""
        def __init__(self, broken):
            self.broken = broken
            self.sent = []

        async def edit_message_text(self, text, reply_markup=None, parse_mode=None):
            if parse_mode is not None and self.broken:
                raise ValueError("BadRequest: Can't parse entities")
            self.sent.append(("markdown" if parse_mode else "plain", text))

    class BrokenMsg:
        def __init__(self, broken):
            self.broken = broken
            self.sent = []

        async def reply_text(self, text, reply_markup=None, parse_mode=None):
            if parse_mode is not None and self.broken:
                raise ValueError("BadRequest: Can't parse entities")
            self.sent.append(("markdown" if parse_mode else "plain", text))

    broken_text = "Broken _italic_ with `code` and *bold"

    bq = BrokenQuery(broken=True)
    from src.bot import safe_edit
    r = await safe_edit(bq, broken_text)
    mode = bq.sent[-1][0] if bq.sent else "none"
    print(f"  safe_edit  -> {'✅' if r and mode == 'plain' else '❌'} (mode={mode})")
    ok &= (r and mode == "plain")

    class BrokenUpdate:
        def __init__(self, broken):
            self.message = BrokenMsg(broken)

    from src.bot import safe_reply
    bu = BrokenUpdate(broken=True)
    r = await safe_reply(bu, broken_text)
    mode = bu.message.sent[-1][0] if bu.message.sent else "none"
    print(f"  safe_reply -> {'✅' if r and mode == 'plain' else '❌'} (mode={mode})")
    ok &= (r and mode == "plain")

    class BrokenBot:
        def __init__(self, broken):
            self.broken = broken
            self.sent = []

        async def send_message(self, chat_id, text, reply_markup=None, parse_mode=None):
            if parse_mode is not None and self.broken:
                raise ValueError("BadRequest: Can't parse entities")
            self.sent.append(("markdown" if parse_mode else "plain", text))

    from src.bot import safe_send
    bb = BrokenBot(broken=True)
    r = await safe_send(bb, 123, broken_text)
    mode = bb.sent[-1][0] if bb.sent else "none"
    print(f"  safe_send  -> {'✅' if r and mode == 'plain' else '❌'} (mode={mode})")
    ok &= (r and mode == "plain")

    print("=" * 55)
    print("✅ SEMUA OK" if ok else "❌ ADA MASALAH")
    print("=" * 55)

    # ── Restore .env & scheduler state ──
    if env_backup and os.path.exists(env_backup):
        shutil.copy2(env_backup, env.ENV_PATH)
        os.remove(env_backup)
        print("✅ .env dipulihkan")
    sched.save_state(sched_backup)

    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
