import sqlite3
import os

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATABASE = os.path.join(BASE_DIR, "app.db")

def init_db():
    conn = sqlite3.connect(DATABASE)
    cursor = conn.cursor()

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS users (
        user_id INTEGER PRIMARY KEY AUTOINCREMENT,
        email TEXT NOT NULL UNIQUE,
        password TEXT NOT NULL,
        parent_name TEXT NOT NULL,
        child_name TEXT NOT NULL,
        child_dob TEXT NOT NULL,
        terms_check INTEGER NOT NULL,
        profile_icon TEXT DEFAULT 'profileicon.png',
        current_activity_id INTEGER
    )
    """)

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS scene (
        scene_id INTEGER PRIMARY KEY AUTOINCREMENT,
        scene_name TEXT NOT NULL,
        scene_image TEXT,
        description TEXT
    )
    """)

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS activity (
        activity_id INTEGER PRIMARY KEY AUTOINCREMENT,
        scene_id INTEGER NOT NULL,
        activity_name TEXT NOT NULL,
        description TEXT,
        activity_order INTEGER NOT NULL,
        level_of_realism INTEGER,
        is_active BOOLEAN DEFAULT 1,
        time_recommended INTEGER,
        character_active TEXT,
        total_levels_of_realism INTEGER,
        template_file TEXT,
        FOREIGN KEY (scene_id) REFERENCES scene(scene_id)
    )
    """)

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS progress (
        progress_id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER NOT NULL,
        activity_id INTEGER NOT NULL,
        is_unlocked BOOLEAN DEFAULT 0,
        is_completed BOOLEAN DEFAULT 0,
        started_at TIMESTAMP,
        completed_at TIMESTAMP,
        words_spoken INTEGER DEFAULT 0,
        minutes_spoken REAL DEFAULT 0,
        active_minutes REAL DEFAULT 0,
        time_spent_on_activity REAL DEFAULT 0,
        FOREIGN KEY (user_id) REFERENCES users(user_id),
        FOREIGN KEY (activity_id) REFERENCES activity(activity_id),
        UNIQUE(user_id, activity_id)
    )
    """)

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS session_log (
        session_id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER NOT NULL,
        activity_id INTEGER NOT NULL,
        words_spoken INTEGER DEFAULT 0,
        minutes_spoken REAL DEFAULT 0,
        active_minutes REAL DEFAULT 0,
        completed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (user_id) REFERENCES users(user_id),
        FOREIGN KEY (activity_id) REFERENCES activity(activity_id)
    )
    """)

    conn.commit()
    conn.close()

    print("Database initialized successfully.")


if __name__ == "__main__":
    init_db()
