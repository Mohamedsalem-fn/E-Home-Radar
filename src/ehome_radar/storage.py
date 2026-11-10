# -*- coding: utf-8 -*-
# -------------------------------------------------------------------------------
# Author: Mohamed Salem (Expert AI Engineer & Automation Architect)
# Focus: AI Engineering | Automation | Agentic Systems
# Copyright (c) 2026. All Rights Reserved.
# -------------------------------------------------------------------------------
"""SQLite persistence (WAL)."""
from __future__ import annotations

import sqlite3
import threading
import time
from pathlib import Path
from typing import List

from .models import Event, Reading

SCHEMA = """
CREATE TABLE IF NOT EXISTS events(id INTEGER PRIMARY KEY, start REAL, end REAL, peak REAL);
CREATE TABLE IF NOT EXISTS samples(ts REAL, raw REAL, score REAL, state TEXT);
CREATE INDEX IF NOT EXISTS ix_samples_ts ON samples(ts);
CREATE INDEX IF NOT EXISTS ix_events_start ON events(start);
"""


class Storage:
    def __init__(self, path: str, retention_days: int = 30):
        if path != ":memory:":
            p = Path(path).expanduser()
            p.parent.mkdir(parents=True, exist_ok=True)
            path = str(p)
        self.db = sqlite3.connect(path, check_same_thread=False)
        self.lock = threading.Lock()
        with self.lock:
            if path != ":memory:":
                self.db.execute("PRAGMA journal_mode=WAL")
            self.db.executescript(SCHEMA)
        self.retention = retention_days * 86400

    def add_sample(self, r: Reading) -> None:
        with self.lock:
            self.db.execute("INSERT INTO samples VALUES(?,?,?,?)", (r.ts, r.raw, r.score, r.state.value))
            self.db.commit()

    def add_event(self, e: Event) -> int:
        with self.lock:
            cur = self.db.execute("INSERT INTO events(start,end,peak) VALUES(?,?,?)", (e.start, e.end, e.peak_score))
            self.db.commit()
            return int(cur.lastrowid)

    def events(self, limit: int = 100, since: float = 0.0) -> List[dict]:
        with self.lock:
            rows = self.db.execute(
                "SELECT id,start,end,peak FROM events WHERE start>=? ORDER BY start DESC LIMIT ?",
                (since, limit),
            ).fetchall()
        return [dict(id=i, start=s, end=e, duration=round(e - s, 2), peak=round(p, 1)) for i, s, e, p in rows]

    def samples(self, since: float, limit: int = 5000) -> List[dict]:
        with self.lock:
            rows = self.db.execute(
                "SELECT ts,raw,score,state FROM samples WHERE ts>=? ORDER BY ts LIMIT ?", (since, limit)
            ).fetchall()
        return [dict(ts=t, raw=r, score=s, state=st) for t, r, s, st in rows]

    def purge(self) -> int:
        cut = time.time() - self.retention
        with self.lock:
            a = self.db.execute("DELETE FROM samples WHERE ts<?", (cut,)).rowcount
            b = self.db.execute("DELETE FROM events WHERE start<?", (cut,)).rowcount
            self.db.commit()
        return a + b

    def close(self) -> None:
        with self.lock:
            self.db.close()

