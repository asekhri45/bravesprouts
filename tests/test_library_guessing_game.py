"""Coverage for the Library Guessing Game ("Classroom Guessing Game" in the
UI).

Covers two fixes:

1. The reliability migration's completion-path fix:
   make_library_guessing_game_correct_round_response() previously let a
   goodbye TTS failure AFTER a successful round-save/unlock write propagate
   as a bare success:false 500 -- indistinguishable from the writes
   themselves failing, even though the child's progress and the next
   activity's unlock had already committed. Also covers the transcribe
   endpoint's format/timeout handling, matching the fix already applied to
   the other four migrated games.

2. The round-3 secret-object resolution bug: get_library_guessing_game_profile()
   used to normalize the stored secret_object through
   normalize_library_guessing_text(), which turns underscores into spaces --
   so the round-3 preset object "glue_stick" never matched its own
   snake_case dict key and silently fell back to "pencil" on every request,
   making round 3 unplayable as intended. resolve_library_guessing_object_key()
   fixes this by normalizing to the canonical snake_case key first (handling
   spaces/hyphens/underscores/case), falling back to alias matching only for
   values that still don't resolve.
"""
import io
from unittest.mock import patch

import httpx
from conftest import login_as_user

import app as app_module


LIBRARY_GUESSING_GAME_ACTIVITY_ID = 6


def _setup_library_guessing_game_activity():
    """LIBRARY_GUESSING_GAME_NEXT_ACTIVITY_ID is a fixed constant (7), not
    "whatever is next in sequence" -- the temp DB needs a real activity row
    at that exact id, plus one at the fixed id this test uses for the game
    itself, since save_library_guessing_game_progress_for_user() looks the
    activity up by activity_name rather than a passed-in id.
    """
    conn = app_module.get_db_connection()
    cur = conn.cursor()

    cur.execute("INSERT INTO scene (scene_name) VALUES ('star_scene')")
    scene_id = cur.lastrowid

    cur.execute(
        "INSERT INTO activity (activity_id, scene_id, activity_name, activity_order, is_active, template_file) "
        "VALUES (?, ?, 'library_guessing_game', 1, 1, 'library_guessing_game.html')",
        (LIBRARY_GUESSING_GAME_ACTIVITY_ID, scene_id),
    )
    cur.execute(
        "INSERT INTO activity (activity_id, scene_id, activity_name, activity_order, is_active, template_file) "
        f"VALUES ({app_module.LIBRARY_GUESSING_GAME_NEXT_ACTIVITY_ID}, ?, 'restaurant_worker_game', 2, 1, 'restaurant_worker_game.html')",
        (scene_id,),
    )

    conn.commit()
    conn.close()


def _client_at_final_round(app_client, make_user):
    user_id = make_user()
    login_as_user(app_client, user_id)

    conn = app_module.get_db_connection()
    cur = conn.cursor()
    cur.execute(
        "INSERT INTO progress (user_id, activity_id, is_unlocked, is_completed) VALUES (?, ?, 1, 0)",
        (user_id, LIBRARY_GUESSING_GAME_ACTIVITY_ID),
    )
    conn.commit()
    conn.close()

    game_state = app_module.get_library_guessing_game_default_state(
        rounds_completed=app_module.LIBRARY_GUESSING_GAME_MAX_ROUNDS - 1
    )
    assert game_state["secret_object"] == "glue_stick"

    with app_client.session_transaction() as sess:
        sess["library_guessing_game_history"] = []
        sess["library_guessing_game_state"] = game_state

    return app_client, user_id


def _post_correct_direct_guess(client):
    return client.post(
        "/api/library-guessing-game/message",
        json={
            "event_type": "child_answer",
            "child_response": "is it a glue stick",
            "response_mode": "open_hint",
        },
    )


def _progress_row(user_id, activity_id):
    conn = app_module.get_db_connection()
    cur = conn.cursor()
    cur.execute(
        "SELECT is_completed, is_unlocked, library_guessing_game_rounds_completed FROM progress "
        "WHERE user_id = ? AND activity_id = ?",
        (user_id, activity_id),
    )
    row = cur.fetchone()
    conn.close()
    return dict(row) if row else None


def _fake_tts_bytes(*args, **kwargs):
    return b"fake-mp3-bytes"


def test_final_round_completion_with_successful_tts(app_client, make_user):
    _setup_library_guessing_game_activity()
    client, user_id = _client_at_final_round(app_client, make_user)

    with patch.object(app_module, "generate_library_guessing_voice_elevenlabs", side_effect=_fake_tts_bytes):
        resp = _post_correct_direct_guess(client)

    assert resp.status_code == 200
    body = resp.get_json()
    assert body["success"] is True
    assert body["session_done"] is True
    assert body["next_url"].endswith("/dashboard")
    assert body["audio"], "expected real audio (base64 data URI) when TTS succeeds"

    row = _progress_row(user_id, LIBRARY_GUESSING_GAME_ACTIVITY_ID)
    assert row["is_completed"] == 1
    assert row["library_guessing_game_rounds_completed"] == app_module.LIBRARY_GUESSING_GAME_MAX_ROUNDS

    next_row = _progress_row(user_id, app_module.LIBRARY_GUESSING_GAME_NEXT_ACTIVITY_ID)
    assert next_row["is_unlocked"] == 1


def test_final_round_completion_with_tts_failure_still_returns_next_url(app_client, make_user):
    _setup_library_guessing_game_activity()
    client, user_id = _client_at_final_round(app_client, make_user)

    with patch.object(
        app_module, "generate_library_guessing_voice_elevenlabs", side_effect=RuntimeError("elevenlabs down")
    ):
        resp = _post_correct_direct_guess(client)

    assert resp.status_code == 200
    body = resp.get_json()
    assert body["success"] is True
    assert body["session_done"] is True
    assert body["next_url"].endswith("/dashboard")
    assert body["audio_parts"] == []
    assert body["audio_available"] is False
    assert body["error_category"] == "tts_unavailable"

    # Progress/unlock writes already committed before the TTS attempt --
    # must not be lost or left un-saved just because the goodbye line failed.
    row = _progress_row(user_id, LIBRARY_GUESSING_GAME_ACTIVITY_ID)
    assert row["is_completed"] == 1

    next_row = _progress_row(user_id, app_module.LIBRARY_GUESSING_GAME_NEXT_ACTIVITY_ID)
    assert next_row["is_unlocked"] == 1


def test_final_round_db_failure_never_falsely_reports_success(app_client, make_user):
    _setup_library_guessing_game_activity()
    client, _user_id = _client_at_final_round(app_client, make_user)

    with patch.object(
        app_module, "save_library_guessing_game_progress_for_user", side_effect=RuntimeError("db write failed")
    ):
        resp = _post_correct_direct_guess(client)

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
        return_value=_fake_transcript("a pencil"),
    ) as mock_create:
        resp = app_client.post(
            "/api/library-guessing-game/transcribe",
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
            "/api/library-guessing-game/transcribe",
            data={"audio": (io.BytesIO(b"fake-audio-bytes"), "child-response.webm")},
            content_type="multipart/form-data",
        )

    assert resp.status_code == 504
    body = resp.get_json()
    assert body["success"] is False
    assert body["error_category"] == "transcription_timeout"


def test_glue_stick_underscore_resolves_correctly():
    game_state = {"secret_object": "glue_stick"}

    profile = app_module.get_library_guessing_game_profile(game_state)

    assert game_state["secret_object"] == "glue_stick"
    assert profile is app_module.LIBRARY_GUESSING_GAME_OBJECT_PROFILES["glue_stick"]


def test_glue_stick_with_space_resolves_correctly():
    game_state = {"secret_object": "glue stick"}

    profile = app_module.get_library_guessing_game_profile(game_state)

    assert game_state["secret_object"] == "glue_stick"
    assert profile is app_module.LIBRARY_GUESSING_GAME_OBJECT_PROFILES["glue_stick"]


def test_glue_stick_with_hyphen_and_mixed_case_resolves_correctly():
    game_state = {"secret_object": "Glue-Stick"}

    profile = app_module.get_library_guessing_game_profile(game_state)

    assert game_state["secret_object"] == "glue_stick"
    assert profile is app_module.LIBRARY_GUESSING_GAME_OBJECT_PROFILES["glue_stick"]


def test_pencil_and_backpack_still_resolve_correctly():
    pencil_state = {"secret_object": "pencil"}
    backpack_state = {"secret_object": "backpack"}

    pencil_profile = app_module.get_library_guessing_game_profile(pencil_state)
    backpack_profile = app_module.get_library_guessing_game_profile(backpack_state)

    assert pencil_state["secret_object"] == "pencil"
    assert pencil_profile is app_module.LIBRARY_GUESSING_GAME_OBJECT_PROFILES["pencil"]

    assert backpack_state["secret_object"] == "backpack"
    assert backpack_profile is app_module.LIBRARY_GUESSING_GAME_OBJECT_PROFILES["backpack"]


def test_invalid_object_falls_back_to_pencil():
    game_state = {"secret_object": "not_a_real_classroom_object"}

    profile = app_module.get_library_guessing_game_profile(game_state)

    assert game_state["secret_object"] == "pencil"
    assert profile is app_module.LIBRARY_GUESSING_GAME_OBJECT_PROFILES["pencil"]


def test_resolve_library_guessing_object_key_handles_missing_value():
    assert app_module.resolve_library_guessing_object_key(None) is None
    assert app_module.resolve_library_guessing_object_key("") is None
