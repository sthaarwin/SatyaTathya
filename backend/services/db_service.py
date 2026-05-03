import sqlite3
import os

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
        
    conn.commit()
    conn.close()

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
