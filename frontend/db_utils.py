import sqlite3
from datetime import datetime

DB_NAME = "history.db"

def init_db():
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute("""
        CREATE TABLE IF NOT EXISTS summaries (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            date TEXT,
            source_type TEXT,
            input_source TEXT,
            summary_text TEXT,
            language TEXT,
            summary_type TEXT
        )
    """)
    conn.commit()
    conn.close()

def save_summary(source_type, input_source, summary_text, language, summary_type):
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute("""
        INSERT INTO summaries (date, source_type, input_source, summary_text, language, summary_type)
        VALUES (?, ?, ?, ?, ?, ?)
    """, (datetime.now().strftime("%Y-%m-%d %H:%M:%S"), source_type, input_source, summary_text, language, summary_type))
    conn.commit()
    conn.close()

def load_summaries():
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute("SELECT * FROM summaries ORDER BY date DESC")
    results = c.fetchall()
    conn.close()
    return results
