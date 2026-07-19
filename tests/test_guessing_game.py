"""Coverage for the Guessing Game reliability migration: the completion
path's TTS-failure fallback (this game generates TTS inline via
generate_star_voice_elevenlabs rather than a cached-file helper, so a
failure there is a live external-API failure, not a cache miss), and the
transcribe endpoint's format/timeout handling.
"""
import io
from unittest.mock import MagicMock, patch

import httpx
from conftest import login_as_user

import app as app_module


def _setup_guessing_game_activity():
    """GUESSING_GAME_NEXT_ACTIVITY_ID is a fixed constant (4), not "whatever
    is next in sequence" -- the temp DB needs a real activity row at that
    exact id for the unlock step to have something to unlock.
    """
    conn = app_module.get_db_connection()
    cur = conn.cursor()

    cur.execute("INSERT INTO scene (scene_name) VALUES ('star_scene')")
    scene_id = cur.lastrowid

    cur.execute(
        "INSERT INTO activity (activity_id, scene_id, activity_name, activity_order, is_active, template_file) "
        "VALUES (3, ?, 'guessing_game', 1, 1, 'guessing_game.html')",
        (scene_id,),
    )
    cur.execute(
        "INSERT INTO activity (activity_id, scene_id, activity_name, activity_order, is_active, template_file) "
        f"VALUES ({app_module.GUESSING_GAME_NEXT_ACTIVITY_ID}, ?, 'drawing_game', 2, 1, 'drawing_game.html')",
        (scene_id,),
    )

    conn.commit()
    conn.close()


def _client_at_final_round(app_client, make_user):
    user_id = make_user()
    login_as_user(app_client, user_id)

    # save_guessing_game_progress_for_user() only UPDATEs an existing
    # progress row (it doesn't INSERT OR IGNORE first, unlike most of the
    # other games' completion helpers) -- create one, matching what
    # real gameplay would already have from opening the activity.
    conn = app_module.get_db_connection()
    cur = conn.cursor()
    cur.execute(
        "INSERT INTO progress (user_id, activity_id, is_unlocked, is_completed) VALUES (?, 3, 1, 0)",
        (user_id,),
    )
    conn.commit()
    conn.close()

    with app_client.session_transaction() as sess:
        sess["guessing_game_history"] = []
        sess["guessing_game_state"] = {
            "rounds_completed": app_module.GUESSING_GAME_MAX_ROUNDS - 1,
            "secret_animal": "dog",
            "used_animals": [],
        }

    return app_client, user_id


def _fake_tts_bytes(_text):
    return b"fake-mp3-bytes"


def _progress_row(user_id, activity_id):
    conn = app_module.get_db_connection()
    cur = conn.cursor()
    cur.execute(
        "SELECT is_completed, is_unlocked, guessing_game_rounds_completed FROM progress "
        "WHERE user_id = ? AND activity_id = ?",
        (user_id, activity_id),
    )
    row = cur.fetchone()
    conn.close()
    return dict(row) if row else None


def _post_correct_guess(client):
    # Matches the app.py:11483 "reveal_choice" + "child_answer" +
    # is_yes_response(...) branch, which is the one that calls
    # make_guessing_game_correct_round_response() -- the actual guess
    # classification logic that reaches this branch in real gameplay is
    # deep, scripted conversation state, so the test drives this exact
    # branch directly rather than trying to replay a full round.
    return client.post(
        "/api/guessing-game/message",
        json={
            "event_type": "child_answer",
            "child_response": "yes",
            "response_mode": "reveal_choice",
        },
    )


def test_final_round_completion_with_successful_tts(app_client, make_user):
    _setup_guessing_game_activity()
    client, user_id = _client_at_final_round(app_client, make_user)

    with patch.object(app_module, "generate_star_voice_elevenlabs", side_effect=_fake_tts_bytes):
        with patch.object(app_module, "is_yes_response", return_value=True):
            resp = _post_correct_guess(client)

    assert resp.status_code == 200
    body = resp.get_json()
    assert body["success"] is True
    assert body["session_done"] is True
    assert body["next_url"].endswith("/dashboard")
    assert body["audio"], "expected real audio (base64 data URI) when TTS succeeds"
    assert body.get("audio_available", True) is not False

    row = _progress_row(user_id, 3)
    assert row["is_completed"] == 1

    next_row = _progress_row(user_id, app_module.GUESSING_GAME_NEXT_ACTIVITY_ID)
    assert next_row["is_unlocked"] == 1


def test_final_round_completion_with_tts_failure_still_returns_next_url(app_client, make_user):
    _setup_guessing_game_activity()
    client, user_id = _client_at_final_round(app_client, make_user)

    with patch.object(app_module, "generate_star_voice_elevenlabs", side_effect=RuntimeError("elevenlabs down")):
        with patch.object(app_module, "is_yes_response", return_value=True):
            resp = _post_correct_guess(client)

    assert resp.status_code == 200
    body = resp.get_json()
    assert body["success"] is True
    assert body["session_done"] is True
    assert body["next_url"].endswith("/dashboard")
    assert body["audio_parts"] == []
    assert body["audio_available"] is False
    assert body["error_category"] == "tts_unavailable"

    # Progress already committed before the TTS attempt -- must not be
    # lost or left un-saved just because the goodbye line failed.
    row = _progress_row(user_id, 3)
    assert row["is_completed"] == 1

    next_row = _progress_row(user_id, app_module.GUESSING_GAME_NEXT_ACTIVITY_ID)
    assert next_row["is_unlocked"] == 1


def test_final_round_db_failure_never_falsely_reports_success(app_client, make_user):
    _setup_guessing_game_activity()
    client, _user_id = _client_at_final_round(app_client, make_user)

    # save_guessing_game_progress_for_user() has no internal try/except --
    # a failure there must propagate as a genuine error, not a disguised
    # success.
    with patch.object(
        app_module, "save_guessing_game_progress_for_user", side_effect=RuntimeError("db write failed")
    ):
        with patch.object(app_module, "is_yes_response", return_value=True):
            resp = _post_correct_guess(client)

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
        return_value=_fake_transcript("a giraffe"),
    ) as mock_create:
        resp = app_client.post(
            "/api/guessing-game/transcribe",
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
            "/api/guessing-game/transcribe",
            data={"audio": (io.BytesIO(b"fake-audio-bytes"), "child-response.webm")},
            content_type="multipart/form-data",
        )

    assert resp.status_code == 504
    body = resp.get_json()
    assert body["success"] is False
    assert body["error_category"] == "transcription_timeout"
