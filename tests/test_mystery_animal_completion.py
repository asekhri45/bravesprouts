"""Coverage for the Mystery Animal completion path's TTS-failure fallback.

At true game completion, progress/unlock is written to the database, and
then a goodbye line is generated via ElevenLabs. These tests pin down the
contract for what happens when that TTS call fails *after* the database
write already committed: the endpoint must still report a recoverable
success with `next_url` (so the client can redirect), never repeat/roll
back the already-successful write, and must never falsely report success
if the database write itself failed.
"""
from unittest.mock import patch

from conftest import login_as_user

import app as app_module


def _setup_mystery_animal_activity(with_next_activity=True):
    """Insert a real, active 'mystery_animal' activity (and, by default, a
    real active activity after it) into the temp DB, mirroring production
    shape closely enough for complete_mystery_animal_and_unlock_next_for_user
    to run its real SQL rather than being mocked.
    """
    conn = app_module.get_db_connection()
    cur = conn.cursor()

    cur.execute("INSERT INTO scene (scene_name) VALUES ('star_scene')")
    scene_id = cur.lastrowid

    cur.execute(
        "INSERT INTO activity (scene_id, activity_name, activity_order, is_active, template_file) "
        "VALUES (?, 'mystery_animal', 1, 1, 'mystery_animal.html')",
        (scene_id,),
    )
    activity_id = cur.lastrowid

    if with_next_activity:
        cur.execute(
            "INSERT INTO activity (scene_id, activity_name, activity_order, is_active, template_file) "
            "VALUES (?, 'guessing_game', 2, 1, 'guessing_game.html')",
            (scene_id,),
        )

    conn.commit()
    conn.close()
    return activity_id


def _client_ready_to_finish_game(app_client, make_user):
    """Log a user in with a session already at the end-of-game round-choice
    decision point, as if they had genuinely played through all required
    rounds -- mirrors real gameplay reaching this point without needing to
    actually drive 9 rounds of conversation through the endpoint.
    """
    user_id = make_user()
    login_as_user(app_client, user_id)

    with app_client.session_transaction() as sess:
        sess["mystery_animal_history"] = []
        sess["mystery_animal_state"] = {
            "rounds_completed": app_module.MYSTERY_ANIMAL_REQUIRED_ROUNDS
        }

    return app_client


def _post_finish_game(client):
    # event_type="no_response" deterministically resolves to choice="stop"
    # once ready_to_unlock_next is true, without depending on the child's
    # actual wording being classified a particular way.
    return client.post(
        "/api/mystery-animal/message",
        json={
            "event_type": "no_response",
            "child_response": "",
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


def test_completion_with_successful_tts_is_unchanged(app_client, make_user, tmp_path, monkeypatch):
    """Baseline: database completion succeeds and TTS succeeds -- normal
    behavior must be preserved exactly (real audio, next_url, success).
    """
    monkeypatch.setattr(app_module, "BASE_DIR", str(tmp_path))
    activity_id = _setup_mystery_animal_activity()
    client = _client_ready_to_finish_game(app_client, make_user)

    with patch.object(
        app_module.eleven_client.text_to_speech,
        "convert",
        return_value=[b"fake-mp3-bytes"],
    ) as mock_tts:
        resp = _post_finish_game(client)

    assert resp.status_code == 200
    body = resp.get_json()
    assert body["success"] is True
    assert body["session_done"] is True
    assert body["next_url"].endswith("/dashboard")
    assert body["audio_parts"], "expected real audio when TTS succeeds"
    assert body.get("audio_available", True) is not False
    assert "error_category" not in body
    mock_tts.assert_called()

    with app_client.session_transaction() as sess:
        user_id = sess["user_id"]
    row = _progress_row(user_id, activity_id)
    assert row["is_completed"] == 1
    assert row["is_unlocked"] == 1


def test_completion_with_tts_failure_still_returns_recoverable_next_url(
    app_client, make_user, tmp_path, monkeypatch
):
    """The core fix: database completion/unlock succeeds, but the goodbye
    line's TTS generation fails. The endpoint must still report a
    recoverable success with next_url (no dead end), and must not repeat
    or roll back the already-successful progress/unlock write.
    """
    monkeypatch.setattr(app_module, "BASE_DIR", str(tmp_path))
    activity_id = _setup_mystery_animal_activity()
    client = _client_ready_to_finish_game(app_client, make_user)

    with patch.object(
        app_module.eleven_client.text_to_speech,
        "convert",
        side_effect=RuntimeError("elevenlabs unavailable"),
    ):
        resp = _post_finish_game(client)

    assert resp.status_code == 200
    body = resp.get_json()
    assert body["success"] is True
    assert body["session_done"] is True
    assert body["next_url"].endswith("/dashboard")
    assert body["audio_parts"] == []
    assert body["audio_available"] is False
    assert body["error_category"] == "tts_unavailable"

    # The already-successful database write must be intact, not repeated
    # or rolled back -- is_completed/is_unlocked are the true record of
    # what happened, independent of whether the goodbye audio played.
    with app_client.session_transaction() as sess:
        user_id = sess["user_id"]
    row = _progress_row(user_id, activity_id)
    assert row["is_completed"] == 1
    assert row["is_unlocked"] == 1


def test_completion_db_failure_never_falsely_reports_success(app_client, make_user):
    """If the database write itself fails, the endpoint must report a
    genuine failure -- it must never return success:true (with or without
    audio) on top of a completion/unlock that never actually committed.
    """
    _setup_mystery_animal_activity()
    client = _client_ready_to_finish_game(app_client, make_user)

    with patch.object(
        app_module,
        "complete_mystery_animal_and_unlock_next_for_user",
        return_value={"ok": False, "next_activity_id": None},
    ):
        # Even if TTS would have succeeded, a failed database write must
        # still surface as a failure -- the mock below proves the success
        # path isn't reached merely because TTS happens to work.
        with patch.object(
            app_module.eleven_client.text_to_speech,
            "convert",
            return_value=[b"fake-mp3-bytes"],
        ):
            resp = _post_finish_game(client)

    assert resp.status_code == 500
    body = resp.get_json()
    assert body["success"] is False
