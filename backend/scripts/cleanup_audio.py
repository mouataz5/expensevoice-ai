#!/usr/bin/env python3
"""
Delete audio files older than AUDIO_RETENTION_DAYS.
Run from cron: 0 2 * * * cd /path/to/backend && python3 scripts/cleanup_audio.py
"""
import os
import sys
from datetime import datetime, timezone, timedelta

# Add backend to path so app.core.config is available
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.core.config import AUDIO_RETENTION_DAYS
from dotenv import load_dotenv

load_dotenv()

AUDIO_DIR = os.getenv("AUDIO_STORAGE_DIR", os.getenv("AUDIO_DIR", "storage/audio"))


def main():
    if AUDIO_RETENTION_DAYS <= 0:
        return
    if not os.path.isdir(AUDIO_DIR):
        return
    cutoff = datetime.now(timezone.utc) - timedelta(days=AUDIO_RETENTION_DAYS)
    removed = 0
    for name in os.listdir(AUDIO_DIR):
        path = os.path.join(AUDIO_DIR, name)
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
        print(f"Removed {removed} old audio file(s) from {AUDIO_DIR}")


if __name__ == "__main__":
    main()
