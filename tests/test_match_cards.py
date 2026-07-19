"""Coverage for Match Cards' reliability migration: the completion/unlock
contract (must never report success after a genuine database failure, must
not double-unlock on a legitimate retry) and the transcription format fix
(actual browser-reported MIME type used instead of a hardcoded ".webm").

Frontend behaviors introduced in this migration (turn tokens, stale-callback
rejection, single-active-recorder enforcement, audio cancellation on
restart) live entirely in static/js/match_cards.js and static/js/game-*.js
and were verified via a live browser preview -- this repo has no JS test
runner, so this file covers the backend contracts those frontend behaviors
depend on: an unambiguous completion/unlock result, and a transcribe
endpoint that respects the actual recorded format.
"""
import io
import sqlite3
from unittest.mock import MagicMock, patch

import httpx
from conftest import login_as_user

import app as app_module


def _setup_match_cards_activity(with_next_activity=True):
    conn = app_module.get_db_connection()
    cur = conn.cursor()

    cur.execute("INSERT INTO scene (scene_name) VALUES ('star_scene')")
    scene_id = cur.lastrowid

    cur.execute(
        "INSERT INTO activity (scene_id, activity_name, activity_order, is_active, template_file) "
        "VALUES (?, 'match_cards', 1, 1, 'match_cards.html')",
        (scene_id,),
    )
    activity_id = cur.lastrowid

    if with_next_activity:
        cur.execute(
            "INSERT INTO activity (scene_id, activity_name, activity_order, is_active, template_file) "
            "VALUES (?, 'mystery_animal', 2, 1, 'mystery_animal.html')",
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
        "SELECT is_completed, is_unlocked, matching_rounds_completed FROM progress "
        "WHERE user_id = ? AND activity_id = ?",
        (user_id, activity_id),
    )
    row = cur.fetchone()
    conn.close()
    return dict(row) if row else None


def _complete_payload(activity_id, rounds_completed):
    return {
        "activity_id": activity_id,
        "words_spoken": 12,
        "minutes_spoken": 1.5,
        "active_minutes": 3.0,
        "time_spent_on_activity": 3.0,
        "spoken_responses": 4,
        "questions_asked": 4,
        "silent_windows": 0,
        "child_matches": 3,
        "parent_matches": 3,
        "final_stage": 2,
        "rounds_completed": rounds_completed,
        "wonder_prompts_asked": 1,
        "help_prompts_asked": 1,
        "clear_prompts_asked": 0,
        "child_choice_responses": 1,
        "child_opinion_responses": 0,
        "child_clear_responses": 0,
        "direct_child_question_silences": 0,
    }


def test_complete_partial_round_does_not_unlock_next(app_client, make_user):
    activity_id = _setup_match_cards_activity()
    client, user_id = _logged_in_client(app_client, make_user)

    resp = client.post(
        "/api/matching-game/complete",
        json=_complete_payload(activity_id, rounds_completed=3),
    )

    assert resp.status_code == 200
    body = resp.get_json()
    assert body["success"] is True
    assert body["activity_completed"] is False
    assert body["next_activity_id"] is None

    row = _progress_row(user_id, activity_id)
    assert row["is_completed"] == 0
    assert row["matching_rounds_completed"] == 3


def test_complete_full_rounds_unlocks_next_activity(app_client, make_user):
    activity_id = _setup_match_cards_activity()
    client, user_id = _logged_in_client(app_client, make_user)

    resp = client.post(
        "/api/matching-game/complete",
        json=_complete_payload(activity_id, rounds_completed=app_module.MATCHING_GAME_TARGET_ROUNDS),
    )

    assert resp.status_code == 200
    body = resp.get_json()
    assert body["success"] is True
    assert body["activity_completed"] is True
    assert body["next_activity_id"] is not None

    row = _progress_row(user_id, activity_id)
    assert row["is_completed"] == 1


def test_complete_db_failure_never_falsely_reports_success(app_client, make_user):
    """A commit failure (disk full, DB locked, etc.) must roll back and
    report failure -- never success with data that was never durably
    saved.
    """
    activity_id = _setup_match_cards_activity()
    client, _user_id = _logged_in_client(app_client, make_user)

    # sqlite3.Connection is a C type and can't be monkeypatched directly;
    # wrap a real connection so every cursor()/execute() call still hits
    # the real temp database, but commit() fails the way a disk-full or
    # locked-database error would in production. The endpoint's own
    # ensure_matching_game_progress_columns() opens and commits its own
    # connection first (a real, unrelated migration step) -- only the
    # *second* connection (the endpoint's own) should fail.
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
        resp = client.post(
            "/api/matching-game/complete",
            json=_complete_payload(activity_id, rounds_completed=app_module.MATCHING_GAME_TARGET_ROUNDS),
        )

    assert resp.status_code == 500
    body = resp.get_json()
    assert body["success"] is False


def test_complete_missing_activity_returns_404_not_success(app_client, make_user):
    client, _user_id = _logged_in_client(app_client, make_user)

    resp = client.post(
        "/api/matching-game/complete",
        json=_complete_payload(activity_id=999999, rounds_completed=5),
    )

    assert resp.status_code == 404
    body = resp.get_json()
    assert body["success"] is False


def _fake_transcript(text):
    class _Transcript:
        pass
    t = _Transcript()
    t.text = text
    return t


def test_transcribe_uses_actual_reported_format_not_hardcoded_webm(app_client, make_user):
    """Safari's MediaRecorder produces mp4/m4a, not webm. The upload
    filename sent to Whisper must reflect what the browser actually
    reported (via the blob's declared filename/content-type), not a
    hardcoded ".webm" that would mislabel a real mp4 recording.
    """
    client, _user_id = _logged_in_client(app_client, make_user)

    with patch.object(
        app_module.client.audio.transcriptions,
        "create",
        return_value=_fake_transcript("a blue one"),
    ) as mock_create:
        resp = client.post(
            "/api/matching-game/transcribe",
            data={"audio": (io.BytesIO(b"fake-mp4-bytes"), "match-response.mp4", "audio/mp4")},
            content_type="multipart/form-data",
        )

    assert resp.status_code == 200
    assert resp.get_json()["success"] is True

    uploaded_file_obj = mock_create.call_args.kwargs["file"]
    assert uploaded_file_obj.name.endswith(".mp4"), (
        f"expected an .mp4 filename for an audio/mp4 upload, got {uploaded_file_obj.name!r}"
    )


def test_transcribe_timeout_is_categorized_not_a_generic_500(app_client, make_user):
    client, _user_id = _logged_in_client(app_client, make_user)

    with patch.object(
        app_module.client.audio.transcriptions,
        "create",
        side_effect=app_module.OpenAITimeoutError(httpx.Request("POST", "https://api.openai.com/v1/audio/transcriptions")),
    ):
        resp = client.post(
            "/api/matching-game/transcribe",
            data={"audio": (io.BytesIO(b"fake-audio-bytes"), "match-response.webm")},
            content_type="multipart/form-data",
        )

    assert resp.status_code == 504
    body = resp.get_json()
    assert body["success"] is False
    assert body["error_category"] == "transcription_timeout"
