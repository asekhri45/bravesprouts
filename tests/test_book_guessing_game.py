"""Coverage for the Book Guessing Game (Mystery Classroom Object backend)
reliability migration: end_classroom_object_call() previously let a TTS
failure AFTER a successful completion/unlock write propagate as a bare
success:false 500 -- indistinguishable from the write itself failing, even
though the child's progress and next-activity unlock had already committed.
Also covers the transcribe endpoint's format/timeout handling, matching the
fix already applied to the other four migrated games.
"""
import io
from unittest.mock import MagicMock, patch

import httpx
from conftest import login_as_user

import app as app_module


def test_classroom_character_uses_exact_drawing_teacher_voice_profile():
    fake_client = MagicMock()
    fake_client.text_to_speech.convert.return_value = [b"audio"]

    voice_environment = {
        "TEACHER_VOICE_ID": "old-classroom-only-voice",
        "LIBRARIAN_VOICE_ID": "shared-drawing-teacher-voice",
        "BOOK_GUESSING_VOICE_ID": "fallback-book-voice",
        "ELEVENLABS_VOICE_ID": "star-voice",
    }

    with patch.object(app_module, "eleven_client", fake_client), patch.dict(
        app_module.os.environ, voice_environment, clear=False
    ):
        app_module.generate_book_guessing_voice_elevenlabs("Let me think.", thinking=True)
        classroom_call = fake_client.text_to_speech.convert.call_args.kwargs

        app_module.generate_drawing_game_voice_elevenlabs("That looks nice.", speaker="teacher")
        drawing_call = fake_client.text_to_speech.convert.call_args.kwargs

    assert classroom_call["voice_id"] == "shared-drawing-teacher-voice"
    assert classroom_call["voice_id"] == drawing_call["voice_id"]
    assert classroom_call["voice_settings"] == drawing_call["voice_settings"]
    assert (
        app_module.get_classroom_object_cached_audio_url.__defaults__[0]
        == "mystery-classroom-object-main-v2"
    )


def _setup_book_guessing_game_activity():
    conn = app_module.get_db_connection()
    cur = conn.cursor()

    cur.execute("INSERT INTO scene (scene_name) VALUES ('star_scene')")
    scene_id = cur.lastrowid

    cur.execute(
        "INSERT INTO activity (scene_id, activity_name, activity_order, is_active, template_file) "
        "VALUES (?, 'book_guessing_game', 1, 1, 'book_guessing_game.html')",
        (scene_id,),
    )
    activity_id = cur.lastrowid

    cur.execute(
        "INSERT INTO activity (scene_id, activity_name, activity_order, is_active, template_file) "
        "VALUES (?, 'restaurant_worker_game', 2, 1, 'restaurant_worker_game.html')",
        (scene_id,),
    )

    conn.commit()
    conn.close()
    return activity_id


def _client_ready_for_round_choice_stop(app_client, make_user):
    user_id = make_user()
    login_as_user(app_client, user_id)

    game_state = app_module.get_classroom_object_default_state(
        rounds_completed=app_module.CLASSROOM_OBJECT_REQUIRED_ROUNDS
    )
    game_state["last_response_mode"] = "round_choice"

    with app_client.session_transaction() as sess:
        sess["mystery_classroom_object_history"] = []
        sess["mystery_classroom_object_state"] = game_state

    return app_client, user_id


def _post_stop_choice(client):
    return client.post(
        "/api/book-guessing-game/message",
        json={
            "event_type": "child_answer",
            "child_response": "stop",
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


def test_complete_and_stop_with_successful_tts(app_client, make_user):
    activity_id = _setup_book_guessing_game_activity()
    client, user_id = _client_ready_for_round_choice_stop(app_client, make_user)

    resp = _post_stop_choice(client)

    assert resp.status_code == 200
    body = resp.get_json()
    assert body["success"] is True
    assert body["session_done"] is True
    assert body["game_complete"] is True
    assert body["next_url"], "expected the unlocked next activity's URL"

    row = _progress_row(user_id, activity_id)
    assert row["is_completed"] == 1


def test_complete_and_stop_with_tts_failure_still_returns_next_url(app_client, make_user):
    """The completion/unlock write must already have committed by the time
    the goodbye TTS is attempted -- a TTS failure here must not be reported
    as a failure on top of a write that actually succeeded.
    """
    activity_id = _setup_book_guessing_game_activity()
    client, user_id = _client_ready_for_round_choice_stop(app_client, make_user)

    with patch.object(
        app_module, "get_classroom_object_cached_audio_url", side_effect=RuntimeError("elevenlabs down")
    ):
        resp = _post_stop_choice(client)

    assert resp.status_code == 200
    body = resp.get_json()
    assert body["success"] is True
    assert body["session_done"] is True
    assert body["game_complete"] is True
    assert body["next_url"], "expected the unlocked next activity's URL even though TTS failed"
    assert body["audio_available"] is False
    assert body["error_category"] == "tts_unavailable"

    row = _progress_row(user_id, activity_id)
    assert row["is_completed"] == 1, "completion write must not be undone by a TTS failure"


def test_complete_and_stop_db_failure_never_falsely_reports_success(app_client, make_user):
    _setup_book_guessing_game_activity()
    client, _user_id = _client_ready_for_round_choice_stop(app_client, make_user)

    with patch.object(
        app_module,
        "complete_classroom_object_and_unlock_next_for_user",
        side_effect=RuntimeError("db write failed"),
    ):
        resp = _post_stop_choice(client)

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
        return_value=_fake_transcript("a backpack"),
    ) as mock_create:
        resp = app_client.post(
            "/api/book-guessing-game/transcribe",
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
            "/api/book-guessing-game/transcribe",
            data={"audio": (io.BytesIO(b"fake-audio-bytes"), "child-response.webm")},
            content_type="multipart/form-data",
        )

    assert resp.status_code == 504
    body = resp.get_json()
    assert body["success"] is False
    assert body["error_category"] == "transcription_timeout"
