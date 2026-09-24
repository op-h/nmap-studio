"""Scan history, saved profiles and settings, on disk."""
from __future__ import annotations

import json
import os
import sqlite3
import time
from contextlib import closing
from dataclasses import dataclass

from .platform_support import config_dir

APP_DIR = config_dir()
DB_PATH = os.path.join(APP_DIR, "history.db")
SETTINGS_PATH = os.path.join(APP_DIR, "settings.json")
PROFILES_PATH = os.path.join(APP_DIR, "profiles.json")


def ensure_dir() -> None:
    os.makedirs(APP_DIR, exist_ok=True)


@dataclass
class HistoryEntry:
    id: int
    title: str
    target: str
    command: str
    started: float
    duration: float
    hosts_up: int
    hosts_total: int
    open_ports: int
    status: str

    @property
    def when(self) -> str:
        return time.strftime("%Y-%m-%d %H:%M", time.localtime(self.started))


_SCHEMA = """
CREATE TABLE IF NOT EXISTS scans (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    title       TEXT NOT NULL,
    target      TEXT,
    command     TEXT,
    config      TEXT,
    xml         TEXT,
    output      TEXT,
    started     REAL,
    duration    REAL,
    hosts_up    INTEGER DEFAULT 0,
    hosts_total INTEGER DEFAULT 0,
    open_ports  INTEGER DEFAULT 0,
    status      TEXT DEFAULT 'finished'
);
CREATE INDEX IF NOT EXISTS scans_started ON scans(started DESC);
"""


def connect() -> sqlite3.Connection:
    ensure_dir()
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.executescript(_SCHEMA)
    return conn


def save_scan(title: str, target: str, command: str, config: dict, xml: str,
              output: str, started: float, duration: float, hosts_up: int,
              hosts_total: int, open_ports: int, status: str) -> int:
    with closing(connect()) as conn, conn:
        cur = conn.execute(
            "INSERT INTO scans (title,target,command,config,xml,output,started,duration,"
            "hosts_up,hosts_total,open_ports,status) VALUES (?,?,?,?,?,?,?,?,?,?,?,?)",
            (title, target, command, json.dumps(config), xml, output, started, duration,
             hosts_up, hosts_total, open_ports, status))
        return int(cur.lastrowid)


def list_scans(search: str = "", limit: int = 500) -> list[HistoryEntry]:
    sql = ("SELECT id,title,target,command,started,duration,hosts_up,hosts_total,"
           "open_ports,status FROM scans")
    params: tuple = ()
    if search:
        sql += " WHERE title LIKE ? OR target LIKE ? OR command LIKE ?"
        params = (f"%{search}%",) * 3
    sql += " ORDER BY started DESC LIMIT ?"
    with closing(connect()) as conn:
        rows = conn.execute(sql, params + (limit,)).fetchall()
    return [HistoryEntry(**dict(r)) for r in rows]


def load_scan(scan_id: int) -> dict | None:
    with closing(connect()) as conn:
        row = conn.execute("SELECT * FROM scans WHERE id=?", (scan_id,)).fetchone()
    if row is None:
        return None
    data = dict(row)
    try:
        data["config"] = json.loads(data.get("config") or "{}")
    except json.JSONDecodeError:
        data["config"] = {}
    return data


def delete_scan(scan_id: int) -> None:
    with closing(connect()) as conn, conn:
        conn.execute("DELETE FROM scans WHERE id=?", (scan_id,))


def rename_scan(scan_id: int, title: str) -> None:
    with closing(connect()) as conn, conn:
        conn.execute("UPDATE scans SET title=? WHERE id=?", (title, scan_id))


def clear_history() -> None:
    with closing(connect()) as conn, conn:
        conn.execute("DELETE FROM scans")


# ----------------------------------------------------------------- settings
DEFAULT_SETTINGS = {
    "theme": "dark",
    "accent": "#3ba3ff",
    "font_size": 10,
    "mono_size": 10,
    "elevate": "pkexec",
    "confirm_risky_scripts": True,
    "autosave_history": True,
    "wrap_output": False,
    "max_history": 500,
}


def load_settings() -> dict:
    data = dict(DEFAULT_SETTINGS)
    try:
        with open(SETTINGS_PATH) as fh:
            data.update(json.load(fh))
    except (OSError, json.JSONDecodeError):
        pass
    return data


def save_settings(settings: dict) -> None:
    ensure_dir()
    with open(SETTINGS_PATH, "w") as fh:
        json.dump(settings, fh, indent=2)


def load_user_profiles() -> list[dict]:
    try:
        with open(PROFILES_PATH) as fh:
            data = json.load(fh)
            return data if isinstance(data, list) else []
    except (OSError, json.JSONDecodeError):
        return []


def save_user_profiles(profiles: list[dict]) -> None:
    ensure_dir()
    with open(PROFILES_PATH, "w") as fh:
        json.dump(profiles, fh, indent=2)
