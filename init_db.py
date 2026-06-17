import sqlite3
import os

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATABASE = os.path.join(BASE_DIR, "app.db")


def column_exists(cursor, table_name, column_name):
    cursor.execute(f"PRAGMA table_info({table_name})")
    columns = [row[1] for row in cursor.fetchall()]
    return column_name in columns


def add_column_if_missing(cursor, table_name, column_definition):
    column_name = column_definition.split()[0]

    if not column_exists(cursor, table_name, column_name):
        cursor.execute(f"ALTER TABLE {table_name} ADD COLUMN {column_definition}")


def init_db():
    conn = sqlite3.connect(DATABASE)
    cursor = conn.cursor()

    cursor.execute("PRAGMA foreign_keys = ON")

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS users (
        user_id INTEGER PRIMARY KEY AUTOINCREMENT,
        email TEXT NOT NULL UNIQUE,
        password TEXT NOT NULL,
        parent_name TEXT NOT NULL,
        child_name TEXT,
        child_dob TEXT,
        terms_check INTEGER NOT NULL,
        profile_icon TEXT DEFAULT 'profileicon.png',
        current_activity_id INTEGER,
        has_seen_tour INTEGER DEFAULT 0,
        child_age INTEGER,
        parent_pin TEXT
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

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS chat_conversations (
        conversation_id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER NOT NULL,
        title TEXT DEFAULT 'New conversation',
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (user_id) REFERENCES users(user_id)
    )
    """)

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS chat_messages (
        message_id INTEGER PRIMARY KEY AUTOINCREMENT,
        conversation_id INTEGER NOT NULL,
        user_id INTEGER NOT NULL,
        role TEXT NOT NULL,
        content TEXT NOT NULL,
        layout_type TEXT DEFAULT 'quick',
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (conversation_id) REFERENCES chat_conversations(conversation_id),
        FOREIGN KEY (user_id) REFERENCES users(user_id)
    )
    """)

    # Safe migrations for older app.db files.
    # These add missing columns if the table already existed before you updated the schema.
    add_column_if_missing(cursor, "users", "has_seen_tour INTEGER DEFAULT 0")
    add_column_if_missing(cursor, "users", "child_age INTEGER")
    add_column_if_missing(cursor, "users", "parent_pin TEXT")

    add_column_if_missing(cursor, "activity", "time_recommended INTEGER")
    add_column_if_missing(cursor, "activity", "character_active TEXT")
    add_column_if_missing(cursor, "activity", "total_levels_of_realism INTEGER")
    add_column_if_missing(cursor, "activity", "template_file TEXT")

    conn.commit()
    conn.close()

    print("Database initialized successfully.")


if __name__ == "__main__":
    init_db()