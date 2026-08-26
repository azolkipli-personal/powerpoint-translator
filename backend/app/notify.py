"""Telegram completion notifications for long-running jpeigo jobs.

Reads TELEGRAM_BOT_TOKEN from env or ~/.hermes/.env (same machine as Hermes).
Chat ID defaults to Ammar's DM; override with TELEGRAM_CHAT_ID env var.
"""
import asyncio
import json
import os
import time
import urllib.request
from pathlib import Path

_HERMES_ENV = Path.home() / ".hermes" / ".env"
_DEFAULT_CHAT_ID = "38158753"

# Jobs shorter than this don't warrant a ping (user is still watching)
_MIN_ELAPSED_S = 60


def _bot_token() -> str | None:
    tok = os.environ.get("TELEGRAM_BOT_TOKEN")
    if tok:
        return tok
    if _HERMES_ENV.exists():
        try:
            for line in _HERMES_ENV.read_text().splitlines():
                if line.startswith("TELEGRAM_BOT_TOKEN="):
                    return line.split("=", 1)[1].strip()
        except Exception:
            pass
    return None


def _send(text: str) -> None:
    tok = _bot_token()
    if not tok:
        print("[NOTIFY] No Telegram token available, skipping")
        return
    chat_id = os.environ.get("TELEGRAM_CHAT_ID", _DEFAULT_CHAT_ID)
    try:
        req = urllib.request.Request(
            f"https://api.telegram.org/bot{tok}/sendMessage",
            json.dumps({"chat_id": chat_id, "text": text}).encode(),
            {"Content-Type": "application/json"},
        )
        urllib.request.urlopen(req, timeout=10)
        print("[NOTIFY] Telegram notification sent")
    except Exception as e:
        print(f"[NOTIFY] Telegram send failed: {e}")


def maybe_notify_job_done(filename: str, total_runs: int, started_at: float, failed: int = 0) -> None:
    """Fire-and-forget notification if the job ran long enough to be worth pinging."""
    elapsed = time.monotonic() - started_at
    if elapsed < _MIN_ELAPSED_S:
        return

    mins = int(elapsed // 60)
    secs = int(elapsed % 60)
    text = (
        f"✅ *JPEIGO translation complete*\n"
        f"📄 {filename}\n"
        f"🔢 {total_runs} runs · ⏱ {mins}m {secs}s"
    )
    if failed:
        text += f"\n⚠️ {failed} run(s) failed — review before download"

    # Send off the event loop if we're in one, otherwise inline in a thread
    try:
        loop = asyncio.get_running_loop()
        loop.run_in_executor(None, _send, text)
    except RuntimeError:
        import threading
        threading.Thread(target=_send, args=(text,), daemon=True).start()
