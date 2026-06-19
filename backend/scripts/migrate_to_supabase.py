"""
One-time script: dump all local SQLite cache to Supabase.
Run:  python backend/scripts/migrate_to_supabase.py
"""

import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from dotenv import load_dotenv
load_dotenv()

import sqlite3
import json
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

DB_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), "satya_cache.db")

SUPABASE_URL = os.getenv("SUPABASE_URL", "")
SUPABASE_SERVICE_KEY = os.getenv("SUPABASE_SERVICE_ROLE_KEY", "")

if not SUPABASE_URL or not SUPABASE_SERVICE_KEY:
    logger.error("SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY must be set in .env")
    sys.exit(1)

import requests

HEADERS = {
    "apikey": SUPABASE_SERVICE_KEY,
    "Authorization": f"Bearer {SUPABASE_SERVICE_KEY}",
    "Content-Type": "application/json",
    "Prefer": "resolution=merge-duplicates",
}


def push_all(table: str, rows: list[dict]):
    if not rows:
        logger.info(f"  No rows to push for {table}")
        return
    url = f"{SUPABASE_URL}/rest/v1/{table}"
    try:
        resp = requests.post(url, headers=HEADERS, json=rows, timeout=30)
        if resp.status_code in (200, 201, 204):
            logger.info(f"  Pushed {len(rows)} rows to {table}")
        else:
            logger.warning(f"  {table} push returned {resp.status_code}: {resp.text[:200]}")
    except Exception as e:
        logger.error(f"  {table} push failed: {e}")


def migrate():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()

    # --- analysis_cache ---
    logger.info("Migrating analysis_cache...")
    c.execute("SELECT url, video_hash, spoken_claim, written_claim, core_news_claim FROM analysis_cache")
    analysis_rows = []
    for row in c.fetchall():
        analysis_rows.append({
            "url": row[0],
            "video_hash": row[1] or "",
            "spoken_claim": row[2],
            "written_claim": row[3],
            "core_news_claim": row[4],
        })
    push_all("analysis_cache", analysis_rows)

    # --- verification_cache ---
    logger.info("Migrating verification_cache...")
    c.execute("SELECT claim, verification_json FROM verification_cache")
    verif_rows = []
    for row in c.fetchall():
        try:
            verif_rows.append({
                "claim": row[0],
                "verification_json": json.loads(row[1]),
            })
        except json.JSONDecodeError:
            verif_rows.append({
                "claim": row[0],
                "verification_json": row[1],
            })
    push_all("verification_cache", verif_rows)

    conn.close()
    logger.info("Migration complete!")


if __name__ == "__main__":
    migrate()
