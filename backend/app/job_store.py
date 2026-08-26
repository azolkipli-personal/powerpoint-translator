"""SQLite-backed job persistence for jpeigo backend.

Survives backend restarts (OOM kills, deploys) so in-flight browser sessions
can recover their work. Jobs are stored as JSON blobs keyed by job_id.

Usage:
    store = get_job_store()          # singleton
    store.save(job)                  # write-through (throttle progress updates)
    job = store.load(job_id)         # None if missing
    store.load_all()                 # dict of all jobs (startup hydration)
    store.delete(job_id)             # remove (cleanup)
    store.delete_old(hours=24)       # prune stale rows
"""
import json
import sqlite3
import threading
import time
from contextlib import contextmanager
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional

_DB_PATH = Path(__file__).resolve().parent.parent / ".job_store.sqlite3"

_SCHEMA = """
CREATE TABLE IF NOT EXISTS jobs (
    job_id TEXT PRIMARY KEY,
    status TEXT NOT NULL,
    updated_at REAL NOT NULL,
    data TEXT NOT NULL
);
"""

# Progress-only rewrites are throttled to this interval (seconds) to avoid
# hammering SQLite once per run on huge decks. Status changes always write.
_PROGRESS_WRITE_INTERVAL = 2.0


class JobStore:
    def __init__(self, db_path: Path = _DB_PATH):
        self._db_path = db_path
        self._lock = threading.Lock()
        self._last_progress_write: dict[str, float] = {}
        self._last_status: dict[str, str] = {}
        # Eager-connect: fail fast at startup if the DB is unusable.
        with self._conn() as conn:
            conn.executescript(_SCHEMA)

    @contextmanager
    def _conn(self):
        """Yield a connection, commit on success and always close it.

        Note: `with sqlite3.Connection` only commits — it never closes, which
        leaked fds until GC. This wrapper guarantees close on both paths.
        """
        conn = sqlite3.connect(str(self._db_path), timeout=5)
        try:
            conn.execute("PRAGMA journal_mode=WAL")
            conn.execute("PRAGMA synchronous=NORMAL")
            yield conn
            conn.commit()
        finally:
            conn.close()

    def save(self, job) -> None:
        """Persist a TranslationJob. Progress-only updates are throttled;
        status transitions always persist immediately."""
        data = job.model_dump_json()
        status = job.status
        now = time.time()

        with self._lock:
            last_status = self._last_status.get(job.job_id)
            status_changed = last_status != status
            last_write = self._last_progress_write.get(job.job_id, 0)
            if not status_changed and (now - last_write) < _PROGRESS_WRITE_INTERVAL:
                return
            self._last_progress_write[job.job_id] = now
            self._last_status[job.job_id] = status
            with self._conn() as conn:
                conn.execute(
                    "INSERT INTO jobs(job_id, status, updated_at, data) VALUES(?,?,?,?) "
                    "ON CONFLICT(job_id) DO UPDATE SET status=excluded.status, "
                    "updated_at=excluded.updated_at, data=excluded.data",
                    (job.job_id, status, now, data),
                )

    def load(self, job_id: str):
        from app.models import TranslationJob

        with self._conn() as conn:
            row = conn.execute(
                "SELECT data FROM jobs WHERE job_id = ?", (job_id,)
            ).fetchone()
        return TranslationJob.model_validate_json(row[0]) if row else None

    def load_all(self) -> dict:
        from app.models import TranslationJob

        with self._conn() as conn:
            rows = conn.execute("SELECT data FROM jobs").fetchall()
        jobs = {}
        for (data,) in rows:
            try:
                job = TranslationJob.model_validate_json(data)
                jobs[job.job_id] = job
                self._last_status[job.job_id] = job.status
            except Exception as e:
                print(f"  [JOBSTORE] Skipping corrupt row: {e}")
        return jobs

    def delete(self, job_id: str) -> None:
        with self._lock, self._conn() as conn:
            conn.execute("DELETE FROM jobs WHERE job_id = ?", (job_id,))
        self._last_progress_write.pop(job_id, None)
        self._last_status.pop(job_id, None)

    def delete_old(self, hours: int = 24) -> int:
        cutoff = time.time() - hours * 3600
        with self._conn() as conn:
            rows = conn.execute(
                "SELECT job_id FROM jobs WHERE updated_at < ?", (cutoff,)
            ).fetchall()
            if rows:
                conn.executemany(
                    "DELETE FROM jobs WHERE job_id = ?", [(r[0],) for r in rows]
                )
        for (job_id,) in rows or []:
            self._last_progress_write.pop(job_id, None)
            self._last_status.pop(job_id, None)
        return len(rows)


_store: Optional[JobStore] = None


def get_job_store() -> JobStore:
    global _store
    if _store is None:
        _store = JobStore()
    return _store
