"""Coverage for the Restaurant Worker Game reliability migration.

/api/restaurant-game/complete previously had no try/except at all around its
database writes -- a DB failure (disk full, locked database) would propagate
as an unhandled exception instead of a clean success:false response, and the
connection would never be closed/rolled back. These tests cover the fix
(matching the try/except + rollback pattern used by every other migrated
game's completion endpoint), plus the transcribe endpoint's format/timeout
handling.
"""
import io
import sqlite3
from unittest.mock import MagicMock, patch

import httpx
from conftest import login_as_user

import app as app_module


def _setup_restaurant_game_activity(with_next_activity=True):
    conn = app_module.get_db_connection()
    cur = conn.cursor()

    cur.execute("INSERT INTO scene (scene_name) VALUES ('star_scene')")
    scene_id = cur.lastrowid

    cur.execute(
        "INSERT INTO activity (scene_id, activity_name, activity_order, is_active, template_file) "
        "VALUES (?, 'restaurant_worker_game', 1, 1, 'restaurant_worker_game.html')",
        (scene_id,),
    )
    activity_id = cur.lastrowid

    if with_next_activity:
        cur.execute(
            "INSERT INTO activity (scene_id, activity_name, activity_order, is_active, template_file) "
            "VALUES (?, 'mystery_food_item', 2, 1, 'mystery_food_item.html')",
            (scene_id,),
        )

    conn.commit()
    conn.close()
    return activity_id


def _logged_in_client(app_client, make_user):
    user_id = make_user()
    login_as_user(app_client, user_id)
    return app_client, user_id


def _progress_row(user_id, activity_id):
    conn = app_module.get_db_connection()
    cur = conn.cursor()
    cur.execute(
        "SELECT is_completed, is_unlocked FROM progress WHERE user_id = ? AND activity_id = ?",
        (user_id, activity_id),
    )
    row = cur.fetchone()
    conn.close()
    return dict(row) if row else None


def _complete_payload(activity_id):
    return {
        "activity_id": activity_id,
        "words_spoken": 20,
        "minutes_spoken": 2.0,
        "active_minutes": 6.0,
        "time_spent_on_activity": 6.0,
        "spoken_responses": 8,
        "silent_windows": 1,
        "worker_direct_responses": 3,
        "teacher_redirects": 1,
        "total_choices": 4,
        "orders_completed": 8,
        "steps_completed": 24,
    }


def test_complete_with_next_activity_unlocks_it(app_client, make_user):
    activity_id = _setup_restaurant_game_activity(with_next_activity=True)
    client, user_id = _logged_in_client(app_client, make_user)

    resp = client.post("/api/restaurant-game/complete", json=_complete_payload(activity_id))

    assert resp.status_code == 200
    body = resp.get_json()
    assert body["success"] is True
    assert body["next_activity_id"] is not None

    row = _progress_row(user_id, activity_id)
    assert row["is_completed"] == 1

    next_row = _progress_row(user_id, body["next_activity_id"])
    assert next_row["is_unlocked"] == 1


def test_complete_with_no_next_activity_still_reports_success(app_client, make_user):
    activity_id = _setup_restaurant_game_activity(with_next_activity=False)
    client, user_id = _logged_in_client(app_client, make_user)

    resp = client.post("/api/restaurant-game/complete", json=_complete_payload(activity_id))

    assert resp.status_code == 200
    body = resp.get_json()
    assert body["success"] is True
    assert body["next_activity_id"] is None

    row = _progress_row(user_id, activity_id)
    assert row["is_completed"] == 1


def test_complete_db_failure_never_falsely_reports_success(app_client, make_user):
    """Before this migration, a failure here had no try/except at all --
    it would surface as an unhandled 500 with no JSON body and no rollback,
    not a clean success:false response.
    """
    activity_id = _setup_restaurant_game_activity()
    client, _user_id = _logged_in_client(app_client, make_user)

    original_get_db_connection = app_module.get_db_connection
    call_state = {"count": 0}

    def flaky_get_db_connection():
        conn = original_get_db_connection()
        call_state["count"] += 1
        if call_state["count"] < 2:
            return conn
        wrapped = MagicMock(wraps=conn)
        wrapped.commit.side_effect = sqlite3.OperationalError("simulated disk full")
        return wrapped

    with patch.object(app_module, "get_db_connection", side_effect=flaky_get_db_connection):
        resp = client.post("/api/restaurant-game/complete", json=_complete_payload(activity_id))

    assert resp.status_code == 500
    body = resp.get_json()
    assert body["success"] is False


def _fake_transcript(text):
    class _Transcript:
        pass
    t = _Transcript()
    t.text = text
    return t


def test_transcribe_uses_actual_reported_format(app_client, make_user):
    client, _user_id = _logged_in_client(app_client, make_user)

    with patch.object(
        app_module.client.audio.transcriptions,
        "create",
        return_value=_fake_transcript("more cheese please"),
    ) as mock_create:
        resp = client.post(
            "/api/restaurant-game/transcribe",
            data={"audio": (io.BytesIO(b"fake-mp4-bytes"), "restaurant-response.mp4", "audio/mp4")},
            content_type="multipart/form-data",
        )

    assert resp.status_code == 200
    assert resp.get_json()["success"] is True

    uploaded_file_obj = mock_create.call_args.kwargs["file"]
    assert uploaded_file_obj.name.endswith(".mp4")


def test_transcribe_timeout_is_categorized(app_client, make_user):
    client, _user_id = _logged_in_client(app_client, make_user)

    with patch.object(
        app_module.client.audio.transcriptions,
        "create",
        side_effect=app_module.OpenAITimeoutError(httpx.Request("POST", "https://api.openai.com/v1/audio/transcriptions")),
    ):
        resp = client.post(
            "/api/restaurant-game/transcribe",
            data={"audio": (io.BytesIO(b"fake-audio-bytes"), "restaurant-response.webm")},
            content_type="multipart/form-data",
        )

    assert resp.status_code == 504
    body = resp.get_json()
    assert body["success"] is False
    assert body["error_category"] == "transcription_timeout"
