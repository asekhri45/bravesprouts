"""Baseline tests for database initialization and the parent_setup_complete migration.

All against a temp SQLite file -- app.db is never touched.
"""
import sqlite3

import app as app_module
import init_db as init_db_module


def _columns(db_path, table):
    conn = sqlite3.connect(db_path)
    cols = {row[1] for row in conn.execute(f"PRAGMA table_info({table})").fetchall()}
    conn.close()
    return cols


def test_init_db_creates_all_expected_tables(temp_db):
    conn = sqlite3.connect(temp_db)
    tables = {row[0] for row in conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table'"
    ).fetchall()}
    conn.close()

    for expected in ("users", "scene", "activity", "progress", "session_log",
                      "chat_conversations", "chat_messages"):
        assert expected in tables


def test_init_db_is_idempotent(temp_db):
    # temp_db fixture already ran init_db() once; running it again must not error
    init_db_module.init_db()
    init_db_module.init_db()
    cols = _columns(temp_db, "users")
    assert "parent_pin" in cols  # sanity: base schema still intact


def test_users_base_schema_columns_present(temp_db):
    cols = _columns(temp_db, "users")
    for expected in ("user_id", "email", "password", "parent_name", "child_name",
                      "child_dob", "terms_check", "profile_icon",
                      "current_activity_id", "has_seen_tour", "child_age", "parent_pin"):
        assert expected in cols


def test_ensure_parent_setup_column_adds_column(temp_db):
    cols = _columns(temp_db, "users")
    assert "parent_setup_complete" in cols


def test_ensure_parent_setup_column_is_idempotent(temp_db):
    # Calling it repeatedly must not raise (no "duplicate column" error)
    app_module.ensure_parent_setup_column()
    app_module.ensure_parent_setup_column()
    app_module.ensure_parent_setup_column()
    cols = _columns(temp_db, "users")
    assert "parent_setup_complete" in cols


def test_parent_setup_complete_defaults_to_one_for_existing_rows(temp_db, make_user):
    """A row inserted the "old" way (no explicit value) must default to complete.

    This is the crux of backward compatibility: existing pre-migration
    accounts must not be locked out of the dashboard.
    """
    conn = app_module.get_db_connection()
    cur = conn.cursor()
    cur.execute("""
        INSERT INTO users (email, password, parent_name, terms_check)
        VALUES ('legacy@example.test', 'hash', 'Legacy Parent', 1)
    """)
    user_id = cur.lastrowid
    conn.commit()

    row = cur.execute(
        "SELECT parent_setup_complete FROM users WHERE user_id = ?", (user_id,)
    ).fetchone()
    conn.close()

    assert row["parent_setup_complete"] == 1
