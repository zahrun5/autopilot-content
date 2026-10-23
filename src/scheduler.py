"""
Auto Scheduler - generate video otomatis 24/7.

Background thread yang menjalankan pipeline secara berkala.
Simpan state di file JSON supaya tetap jalan setelah bot restart.
"""

import json
import os
import random
import sys
import threading
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

PROJECT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
STATE_FILE = os.path.join(PROJECT_DIR, ".scheduler.json")

# Default: generate tiap 6 jam, random/off (biar tidak kena limit API)
DEFAULT_CONFIG = {
    "enabled": False,
    "interval_hours": 6,
    "random_jitter_minutes": 30,
    "upload": True,
    "niche": "motivasi",
    "last_run": 0,
    "next_run": 0,
    "total_runs": 0,
    "last_error": "",
    "last_video": "",
}


def load_state():
    if os.path.exists(STATE_FILE):
        try:
            with open(STATE_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
            return {**DEFAULT_CONFIG, **data}
        except Exception:
            pass
    return dict(DEFAULT_CONFIG)


def save_state(state):
    with open(STATE_FILE, "w", encoding="utf-8") as f:
        json.dump(state, f, indent=2)


# ── Worker ────────────────────────────────────────────────────

class Scheduler:
    """Scheduler single-instance yang jalan di background thread."""

    def __init__(self, on_done=None, on_error=None):
        self.on_done = on_done      # callback(result) setelah sukses
        self.on_error = on_error    # callback(exception)
        self._thread = None
        self._stop_event = threading.Event()
        self._lock = threading.Lock()

    @property
    def running(self):
        return self._thread is not None and self._thread.is_alive()

    def start(self):
        with self._lock:
            if self.running:
                return False
            self._stop_event.clear()
            self._thread = threading.Thread(target=self._loop, daemon=True)
            self._thread.start()
            return True

    def stop(self):
        self._stop_event.set()
        return True

    def _loop(self):
        while not self._stop_event.is_set():
            state = load_state()
            if not state.get("enabled"):
                # Tidur 30 detik, cek lagi
                self._stop_event.wait(30)
                continue

            now = time.time()
            next_run = state.get("next_run", 0)

            if next_run and now < next_run:
                # Tidur sampai jadwal berikutnya (max 60 detik biar responsif)
                wait = min(60, max(1, next_run - now))
                self._stop_event.wait(wait)
                continue

            # Sudah waktunya jalan
            self._run_once(state)
            time.sleep(5)

    def _run_once(self, state):
        from main import run_pipeline

        niche = state.get("niche", "motivasi")
        try:
            result = run_pipeline(
                niche=niche,
                topik=None,
                skip_upload=not state.get("upload", True),
            )
            state = load_state()
            state["last_run"] = int(time.time())
            state["total_runs"] = state.get("total_runs", 0) + 1
            state["last_error"] = ""
            state["last_video"] = result.get("video_path", "")
            state["next_run"] = self._calc_next(state)
            save_state(state)
            if self.on_done:
                self.on_done(result)
        except Exception as e:
            state = load_state()
            state["last_run"] = int(time.time())
            state["last_error"] = str(e)[:300]
            state["next_run"] = self._calc_next(state)
            save_state(state)
            print(f"[Scheduler] Error: {e}")
            if self.on_error:
                self.on_error(e)

    @staticmethod
    def _calc_next(state):
        hours = state.get("interval_hours", 6)
        jitter = state.get("random_jitter_minutes", 30)
        # Random jitter supaya tidak selalu jam yang sama
        jitter_sec = random.randint(-jitter * 60, jitter * 60)
        return int(time.time() + hours * 3600 + jitter_sec)


# ── API untuk bot ────────────────────────────────────────────

def set_enabled(enabled: bool, interval_hours=None, upload=None, niche=None):
    """Update konfigurasi scheduler."""
    state = load_state()
    was_enabled = state.get("enabled", False)
    state["enabled"] = enabled
    if interval_hours is not None:
        state["interval_hours"] = max(1, int(interval_hours))
    if upload is not None:
        state["upload"] = upload
    if niche is not None:
        state["niche"] = niche

    # Hitung next run
    if enabled and not was_enabled:
        state["next_run"] = Scheduler._calc_next(state)
    elif not enabled:
        state["next_run"] = 0

    save_state(state)
    return state


def get_state():
    return load_state()


def human_next_run(state=None):
    """Format next_run jadi string yang enak dibaca."""
    state = state or load_state()
    if not state.get("enabled"):
        return "⏸️ mati"
    nxt = state.get("next_run", 0)
    if not nxt:
        return "⏳ akan dijalankan sebentar lagi"

    import datetime
    dt = datetime.datetime.fromtimestamp(nxt)
    now = datetime.datetime.now()
    delta = dt - now
    jam = max(0, int(delta.total_seconds() // 3600))
    menit = max(0, int((delta.total_seconds() % 3600) // 60))
    return f"⏰ {dt.strftime('%d/%m %H:%M')} (dalam {jam}j {menit}m)"
