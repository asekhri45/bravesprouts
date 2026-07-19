"""Coverage for the Mystery Food Item reliability migration.

complete_mystery_food_and_unlock_next_for_user() used to return a bare
next_activity_id (or None) -- None meant both "this is legitimately the
last active activity" AND "the database write itself failed" with no way
for the caller to tell them apart, and finish_mystery_food_session()
discarded the return value entirely, unconditionally redirecting to
/dashboard as if completion had succeeded either way. Now the helper
returns {"ok": bool, "next_activity_id": ...} and a failed write raises,
which the route's try/except turns into an honest success:false response.
Also covers the transcribe endpoint's format/timeout handling, matching the
fix already applied to the other five migrated games.
"""
import io
from unittest.mock import patch

import httpx
from conftest import login_as_user

import app as app_module


def _setup_mystery_food_activity(with_next_activity=True):
    conn = app_module.get_db_connection()
    cur = conn.cursor()

    cur.execute("INSERT INTO scene (scene_name) VALUES ('star_scene')")
    scene_id = cur.lastrowid

    cur.execute(
        "INSERT INTO activity (scene_id, activity_name, activity_order, is_active, template_file) "
        "VALUES (?, 'mystery_food_item', 1, 1, 'mystery_food_item.html')",
        (scene_id,),
    )
    activity_id = cur.lastrowid

    if with_next_activity:
        cur.execute(
            "INSERT INTO activity (scene_id, activity_name, activity_order, is_active, template_file) "
            "VALUES (?, 'some_next_game', 2, 1, 'some_next_game.html')",
            (scene_id,),
        )

    conn.commit()
    conn.close()
    return activity_id


def _client_at_final_round_choice(app_client, make_user):
    user_id = make_user()
    login_as_user(app_client, user_id)

    game_state = app_module.get_mystery_food_default_state(
        rounds_completed=app_module.MYSTERY_FOOD_REQUIRED_ROUNDS
    )
    game_state["stage"] = "round_choice"

    with app_client.session_transaction() as sess:
        sess["mystery_food_item_history"] = []
        sess["mystery_food_item_state"] = game_state

    return app_client, user_id


def _post_end_choice(client):
    return client.post(
        "/api/mystery-food-item/message",
        json={
            "event_type": "child_answer",
            "child_response": "end",
            "response_mode": "round_choice",
        },
    )


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


def test_end_at_final_round_completes_and_unlocks_next(app_client, make_user):
    activity_id = _setup_mystery_food_activity(with_next_activity=True)
    client, user_id = _client_at_final_round_choice(app_client, make_user)

    resp = _post_end_choice(client)

    assert resp.status_code == 200
    body = resp.get_json()
    assert body["success"] is True
    assert body["session_done"] is True
    assert body["next_url"].endswith("/dashboard")

    row = _progress_row(user_id, activity_id)
    assert row["is_completed"] == 1


def test_end_at_final_round_with_no_next_activity_still_reports_success(app_client, make_user):
    """A legitimate 'no more games' completion must not look like a
    failure -- this is exactly the case the old bare-None return value
    could not distinguish from a genuine DB failure.
    """
    activity_id = _setup_mystery_food_activity(with_next_activity=False)
    client, user_id = _client_at_final_round_choice(app_client, make_user)

    resp = _post_end_choice(client)

    assert resp.status_code == 200
    body = resp.get_json()
    assert body["success"] is True
    assert body["session_done"] is True

    row = _progress_row(user_id, activity_id)
    assert row["is_completed"] == 1


def test_end_at_final_round_db_failure_never_falsely_reports_success(app_client, make_user):
    _setup_mystery_food_activity()
    client, _user_id = _client_at_final_round_choice(app_client, make_user)

    with patch.object(
        app_module, "complete_mystery_food_and_unlock_next_for_user",
        return_value={"ok": False, "next_activity_id": None},
    ):
        resp = _post_end_choice(client)

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
    user_id = make_user()
    login_as_user(app_client, user_id)

    with patch.object(
        app_module.client.audio.transcriptions,
        "create",
        return_value=_fake_transcript("a hot dog"),
    ) as mock_create:
        resp = app_client.post(
            "/api/mystery-food-item/transcribe",
            data={"audio": (io.BytesIO(b"fake-mp4-bytes"), "child-response.mp4", "audio/mp4")},
            content_type="multipart/form-data",
        )

    assert resp.status_code == 200
    assert resp.get_json()["success"] is True

    uploaded_file_obj = mock_create.call_args.kwargs["file"]
    assert uploaded_file_obj.name.endswith(".mp4")


def test_transcribe_timeout_is_categorized(app_client, make_user):
    user_id = make_user()
    login_as_user(app_client, user_id)

    with patch.object(
        app_module.client.audio.transcriptions,
        "create",
        side_effect=app_module.OpenAITimeoutError(httpx.Request("POST", "https://api.openai.com/v1/audio/transcriptions")),
    ):
        resp = app_client.post(
            "/api/mystery-food-item/transcribe",
            data={"audio": (io.BytesIO(b"fake-audio-bytes"), "child-response.webm")},
            content_type="multipart/form-data",
        )

    assert resp.status_code == 504
    body = resp.get_json()
    assert body["success"] is False
    assert body["error_category"] == "transcription_timeout"
