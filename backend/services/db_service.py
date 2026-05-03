import sqlite3
import os

DB_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), "satya_cache.db")

def init_db():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS analysis_cache
                 (url TEXT PRIMARY KEY, spoken_claim TEXT, written_claim TEXT, core_news_claim TEXT)''')
    conn.commit()
    conn.close()

def get_cached_analysis(url):
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

def save_analysis(url, data):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute('''INSERT OR REPLACE INTO analysis_cache (url, spoken_claim, written_claim, core_news_claim)
                 VALUES (?, ?, ?, ?)''', (url, data.get("spoken_claim"), data.get("written_claim"), data.get("core_news_claim")))
    conn.commit()
    conn.close()
