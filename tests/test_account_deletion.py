"""Tests for the expanded /delete-account route.

Audited tables with a user_id column: users, progress, session_log,
chat_conversations, chat_messages, parent_feedback. This suite proves every
one of them is cleared for the deleted user, and that a second user's rows
in the same tables are left untouched.
"""
import app as app_module
from conftest import login_as_user

USER_LINKED_TABLES = [
    "progress",
    "session_log",
    "chat_conversations",
    "chat_messages",
    "parent_feedback",
]


def _ensure_test_activity():
    """init_db.py only creates the activity/scene table schema -- real
    activity rows are seeded separately in production (not by init_db.py),
    so a fresh temp DB starts with zero rows. Insert one minimal row so
    tests that need a valid activity_id have something to reference.
    """
    conn = app_module.get_db_connection()
    cur = conn.cursor()
    cur.execute("SELECT activity_id FROM activity LIMIT 1")
    row = cur.fetchone()
    if row:
        conn.close()
        return row["activity_id"]

    cur.execute("INSERT INTO scene (scene_name) VALUES ('test_scene')")
    scene_id = cur.lastrowid
    cur.execute(
        "INSERT INTO activity (scene_id, activity_name, activity_order, is_active) VALUES (?, 'test_activity', 1, 1)",
        (scene_id,),
    )
    activity_id = cur.lastrowid
    conn.commit()
    conn.close()
    return activity_id


def _seed_related_rows(user_id):
    activity_id = _ensure_test_activity()

    conn = app_module.get_db_connection()
    cur = conn.cursor()

    cur.execute(
        "INSERT INTO session_log (user_id, activity_id, words_spoken) VALUES (?, ?, 5)",
        (user_id, activity_id),
    )

    cur.execute(
        "INSERT INTO chat_conversations (user_id, title) VALUES (?, 'Test convo')",
        (user_id,),
    )
    conversation_id = cur.lastrowid

    cur.execute(
        "INSERT INTO chat_messages (conversation_id, user_id, role, content) VALUES (?, ?, 'user', 'hello')",
        (conversation_id, user_id),
    )

    cur.execute(
        """
        INSERT INTO parent_feedback (user_id, what_child_enjoyed)
        VALUES (?, 'Everything!')
        """,
        (user_id,),
    )

    conn.commit()
    conn.close()
    return activity_id


def _counts_for_user(user_id):
    conn = app_module.get_db_connection()
    cur = conn.cursor()
    counts = {}
    for table in USER_LINKED_TABLES:
        counts[table] = cur.execute(
            f"SELECT COUNT(*) AS n FROM {table} WHERE user_id = ?", (user_id,)
        ).fetchone()["n"]
    counts["users"] = cur.execute(
        "SELECT COUNT(*) AS n FROM users WHERE user_id = ?", (user_id,)
    ).fetchone()["n"]
    conn.close()
    return counts


def test_delete_account_removes_rows_from_every_linked_table(app_client, make_user):
    user_id = make_user(email="deleteme@example.test")
    activity_id = _ensure_test_activity()
    conn = app_module.get_db_connection()
    cur = conn.cursor()
    cur.execute(
        "INSERT INTO progress (user_id, activity_id, is_unlocked) VALUES (?, ?, 1)",
        (user_id, activity_id),
    )
    conn.commit()
    conn.close()

    _seed_related_rows(user_id)

    before = _counts_for_user(user_id)
    assert before["users"] == 1
    assert before["progress"] >= 1
    assert before["session_log"] >= 1
    assert before["chat_conversations"] >= 1
    assert before["chat_messages"] >= 1
    assert before["parent_feedback"] >= 1

    login_as_user(app_client, user_id, parent_setup_complete=True)
    resp = app_client.post("/delete-account")
    assert resp.status_code == 302
    assert resp.headers["Location"] == "/login"

    after = _counts_for_user(user_id)
    assert after == {table: 0 for table in USER_LINKED_TABLES + ["users"]}


def test_delete_account_does_not_touch_other_users_data(app_client, make_user):
    user_a = make_user(email="deleteA@example.test")
    user_b = make_user(email="keepB@example.test")

    _seed_related_rows(user_a)
    _seed_related_rows(user_b)

    login_as_user(app_client, user_a, parent_setup_complete=True)
    app_client.post("/delete-account")

    after_a = _counts_for_user(user_a)
    after_b = _counts_for_user(user_b)

    assert after_a["users"] == 0
    assert after_b["users"] == 1
    assert after_b["chat_conversations"] >= 1
    assert after_b["chat_messages"] >= 1
    assert after_b["parent_feedback"] >= 1


def test_delete_account_clears_session(app_client, make_user):
    user_id = make_user(email="sessionclear@example.test")
    login_as_user(app_client, user_id, parent_setup_complete=True)
    app_client.post("/delete-account")
    with app_client.session_transaction() as sess:
        assert "user_id" not in sess
