"""SQLite schema management for MedReport."""

from __future__ import annotations

import sqlite3
from pathlib import Path


class SQLiteDatabase:
    """Small SQLite database wrapper for application persistence."""

    def __init__(self, path: Path) -> None:
        self.path = path

    def initialize(self) -> None:
        """Create all baseline tables if they do not exist."""

        self.path.parent.mkdir(parents=True, exist_ok=True)
        with sqlite3.connect(self.path) as connection:
            connection.executescript(
                """
                CREATE TABLE IF NOT EXISTS recent_studies (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    folder TEXT NOT NULL UNIQUE,
                    imported_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
                );
                CREATE TABLE IF NOT EXISTS annotations (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    series_uid TEXT NOT NULL,
                    payload TEXT NOT NULL,
                    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
                );
                CREATE TABLE IF NOT EXISTS reports (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    study_uid TEXT NOT NULL,
                    format TEXT NOT NULL,
                    body TEXT NOT NULL,
                    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
                );
                CREATE TABLE IF NOT EXISTS settings (
                    key TEXT PRIMARY KEY,
                    value TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS bookmarks (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    study_uid TEXT NOT NULL,
                    label TEXT NOT NULL,
                    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
                );
                """
            )

    def add_recent_study(self, folder: Path) -> None:
        """Record or refresh a recently imported study folder."""

        with sqlite3.connect(self.path) as connection:
            connection.execute(
                """
                INSERT INTO recent_studies(folder, imported_at)
                VALUES(?, CURRENT_TIMESTAMP)
                ON CONFLICT(folder) DO UPDATE SET imported_at = CURRENT_TIMESTAMP
                """,
                (str(folder),),
            )
