#!/usr/bin/env python3
"""
Part 3.4: Database backup script for daily/scheduled runs.
- SQLite: copies the DB file to BACKUP_DIR with timestamp.
- PostgreSQL: runs pg_dump to a timestamped file (requires pg_dump on PATH).

Usage:
  cd /path/to/backend && python3 scripts/backup_db.py

Cron example (daily at 2 AM):
  0 2 * * * cd /path/to/backend && python3 scripts/backup_db.py >> /var/log/expensevoice_backup.log 2>&1

Environment:
  DATABASE_URL  - from .env (sqlite or postgres)
  BACKUP_DIR    - directory for backup files (default: backend/backups)
  BACKUP_RETENTION_DAYS - keep only last N days of backups (default: 30, 0 = keep all)
"""
import os
import shutil
import subprocess
import sys
from datetime import datetime, timezone, timedelta

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv

load_dotenv()

from app.core.config import DATABASE_URL

BACKUP_DIR = os.getenv("BACKUP_DIR", os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "backups"))
BACKUP_RETENTION_DAYS = int(os.getenv("BACKUP_RETENTION_DAYS", "30"))


def _timestamp() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")


def backup_sqlite(db_path: str) -> str:
    """Copy SQLite file to BACKUP_DIR with timestamp."""
    os.makedirs(BACKUP_DIR, exist_ok=True)
    base = os.path.basename(db_path)
    name, _ = os.path.splitext(base)
    dest = os.path.join(BACKUP_DIR, f"{name}_{_timestamp()}.db")
    shutil.copy2(db_path, dest)
    return dest


def backup_postgres(url: str) -> str:
    """Run pg_dump and write to BACKUP_DIR. Returns path to backup file."""
    # Parse URL: postgresql://user:pass@host:port/dbname
    os.makedirs(BACKUP_DIR, exist_ok=True)
    dest = os.path.join(BACKUP_DIR, f"expensevoice_{_timestamp()}.sql")
    # pg_dump uses env vars or connection string
    env = os.environ.copy()
    env["PGPASSWORD"] = ""  # clear; we pass via URI if needed
    # Use pg_dump with URI (PostgreSQL 9.3+)
    result = subprocess.run(
        ["pg_dump", "--no-owner", "--no-acl", url, "-f", dest],
        env=env,
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        raise RuntimeError(f"pg_dump failed: {result.stderr or result.stdout}")
    return dest


def cleanup_old_backups():
    """Remove backup files older than BACKUP_RETENTION_DAYS."""
    if BACKUP_RETENTION_DAYS <= 0 or not os.path.isdir(BACKUP_DIR):
        return
    cutoff = datetime.now(timezone.utc) - timedelta(days=BACKUP_RETENTION_DAYS)
    removed = 0
    for name in os.listdir(BACKUP_DIR):
        path = os.path.join(BACKUP_DIR, name)
        if not os.path.isfile(path):
            continue
        mtime = datetime.fromtimestamp(os.path.getmtime(path), tz=timezone.utc)
        if mtime < cutoff:
            try:
                os.remove(path)
                removed += 1
            except OSError:
                pass
    if removed:
        print(f"Removed {removed} old backup(s) from {BACKUP_DIR}")


def main():
    url = (DATABASE_URL or "").strip()
    if not url:
        print("DATABASE_URL not set", file=sys.stderr)
        sys.exit(1)

    try:
        if url.startswith("sqlite"):
            # sqlite:///./expensevoice.db -> expensevoice.db (relative to backend)
            path = url.replace("sqlite:///", "").strip().lstrip("./")
            backend_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
            if not os.path.isabs(path):
                path = os.path.join(backend_dir, path)
            if not os.path.isfile(path):
                print(f"SQLite file not found: {path}", file=sys.stderr)
                sys.exit(1)
            out = backup_sqlite(path)
        elif "postgresql" in url or "postgres" in url:
            out = backup_postgres(url)
        else:
            print("Unsupported DATABASE_URL scheme", file=sys.stderr)
            sys.exit(1)

        print(f"Backup written: {out}")
        cleanup_old_backups()
    except Exception as e:
        print(f"Backup failed: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
