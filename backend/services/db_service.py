import sqlite3
import os
import json

DB_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), "satya_cache.db")

def init_db():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS analysis_cache
                 (url TEXT PRIMARY KEY, spoken_claim TEXT, written_claim TEXT, core_news_claim TEXT)''')
                 
    # Dynamically add video_hash column if it doesn't already exist from older versions
    try:
        c.execute('ALTER TABLE analysis_cache ADD COLUMN video_hash TEXT')
    except sqlite3.OperationalError:
        pass # Column already exists
        
    # Create an index on the video hash to make visual lookups lightning fast
    c.execute('CREATE INDEX IF NOT EXISTS idx_video_hash ON analysis_cache(video_hash)')
    
    # Create verification cache (drop old table if exists with old schema)
    c.execute('DROP TABLE IF EXISTS verification_cache')
    c.execute('''CREATE TABLE IF NOT EXISTS verification_cache
                 (claim TEXT PRIMARY KEY, verification_json TEXT)''')
    
    # Create evidence cache (scraped article text keyed by claim)
    c.execute('''CREATE TABLE IF NOT EXISTS evidence_cache
                 (claim_hash TEXT PRIMARY KEY, evidence_json TEXT, created_at REAL NOT NULL DEFAULT (strftime('%s','now')))''')
        
    conn.commit()
    conn.close()

def get_cached_verification(claim):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute('SELECT verification_json FROM verification_cache WHERE claim = ?', (claim,))
    row = c.fetchone()
    conn.close()
    if row:
        return json.loads(row[0])
    return None

def save_verification(claim, verification_data):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute('''INSERT OR REPLACE INTO verification_cache (claim, verification_json)
                 VALUES (?, ?)''', (claim, json.dumps(verification_data)))
    conn.commit()
    conn.close()

# Initialize tables
init_db()

def get_cached_analysis_by_url(url):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute('SELECT spoken_claim, written_claim, core_news_claim FROM analysis_cache WHERE url = ?', (url,))
    row = c.fetchone()
    conn.close()
    
    if row:
        return {
            "spoken_claim": row[0],
            "written_claim": row[1],
            "core_news_claim": row[2]
        }
    return None

def get_cached_analysis_by_hash(video_hash):
    if not video_hash or "ERROR" in video_hash:
        return None
        
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute('SELECT spoken_claim, written_claim, core_news_claim FROM analysis_cache WHERE video_hash = ?', (video_hash,))
    row = c.fetchone()
    conn.close()
    
    if row:
        return {
            "spoken_claim": row[0],
            "written_claim": row[1],
            "core_news_claim": row[2]
        }
    return None

def save_analysis(url, video_hash, data):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute('''INSERT OR REPLACE INTO analysis_cache (url, video_hash, spoken_claim, written_claim, core_news_claim)
                 VALUES (?, ?, ?, ?, ?)''', (url, video_hash, data.get("spoken_claim"), data.get("written_claim"), data.get("core_news_claim")))
    conn.commit()
    conn.close()

def get_all_cached_analyses():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute('SELECT url, spoken_claim, written_claim, core_news_claim, video_hash FROM analysis_cache')
    rows = c.fetchall()
    conn.close()
    return [{"url": r[0], "spoken_claim": r[1], "written_claim": r[2], "core_news_claim": r[3], "video_hash": r[4]} for r in rows]

def get_cached_evidence(claim_text: str):
    claim_hash = str(hash(claim_text))
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute('SELECT evidence_json FROM evidence_cache WHERE claim_hash = ?', (claim_hash,))
    row = c.fetchone()
    conn.close()
    if row:
        return json.loads(row[0])
    return None

def save_evidence_cache(claim_text: str, evidence_data: list):
    claim_hash = str(hash(claim_text))
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute('''INSERT OR REPLACE INTO evidence_cache (claim_hash, evidence_json, created_at)
                 VALUES (?, ?, strftime('%s','now'))''', (claim_hash, json.dumps(evidence_data)))
    conn.commit()
    conn.close()

def clear_cache():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute('DELETE FROM analysis_cache')
    c.execute('DELETE FROM verification_cache')
    c.execute('DELETE FROM evidence_cache')
    count = c.rowcount
    conn.commit()
    conn.close()
    return count
