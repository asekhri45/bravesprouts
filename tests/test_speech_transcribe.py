"""Coverage for the speech-to-text (audio transcription) backend routes.

These routes previously had zero test coverage. All of them share the same
contract (missing file -> 400, empty file -> 400, success -> 200 with the
transcript text, upstream exception -> 500), so this suite verifies that
contract on /api/matching-game/transcribe (the route backing "Activity 1" /
Match Cards, the one game reported to reliably hear the child) and spot-checks
two of the other voice-enabled activities to confirm they follow the same
contract rather than diverging in response shape or auth requirements.

The real OpenAI Whisper call (client.audio.transcriptions.create) is mocked
throughout -- no network access or API credentials are required to run these.
"""
import io
from unittest.mock import patch

from conftest import login_as_user

import app as app_module


def _logged_in_client(app_client, make_user):
    user_id = make_user()
    login_as_user(app_client, user_id)
    return app_client


def _fake_transcript(text):
    class _Transcript:
        pass
    t = _Transcript()
    t.text = text
    return t


TRANSCRIBE_ROUTES = [
    "/api/matching-game/transcribe",
    "/api/guessing-game/transcribe",
    "/api/mystery-animal/transcribe",
]


def test_matching_game_transcribe_requires_login(app_client):
    """Activity 1's transcribe route must not be reachable while logged out."""
    resp = app_client.post(
        "/api/matching-game/transcribe",
        data={"audio": (io.BytesIO(b"fake-audio-bytes"), "clip.webm")},
        content_type="multipart/form-data",
    )
    assert resp.status_code in (301, 302)
    assert "/login" in resp.headers["Location"]


def test_matching_game_transcribe_missing_audio_field(app_client, make_user):
    client = _logged_in_client(app_client, make_user)

    resp = client.post("/api/matching-game/transcribe", data={})

    assert resp.status_code == 400
    body = resp.get_json()
    assert body["success"] is False
    assert "audio" in body["error"].lower()


def test_matching_game_transcribe_empty_audio_file(app_client, make_user):
    client = _logged_in_client(app_client, make_user)

    resp = client.post(
        "/api/matching-game/transcribe",
        data={"audio": (io.BytesIO(b""), "clip.webm")},
        content_type="multipart/form-data",
    )

    assert resp.status_code == 400
    body = resp.get_json()
    assert body["success"] is False
    assert "empty" in body["error"].lower()


def test_matching_game_transcribe_success(app_client, make_user):
    client = _logged_in_client(app_client, make_user)

    with patch.object(
        app_module.client.audio.transcriptions,
        "create",
        return_value=_fake_transcript("  the yellow one  "),
    ) as mock_create:
        resp = client.post(
            "/api/matching-game/transcribe",
            data={"audio": (io.BytesIO(b"fake-audio-bytes"), "match-response.webm")},
            content_type="multipart/form-data",
        )

    assert resp.status_code == 200
    body = resp.get_json()
    assert body["success"] is True
    # Route strips whitespace before returning the transcript.
    assert body["text"] == "the yellow one"
    mock_create.assert_called_once()
    assert mock_create.call_args.kwargs["model"] == "gpt-4o-mini-transcribe"


def test_matching_game_transcribe_upstream_failure_returns_502_not_a_crash(app_client, make_user):
    """If OpenAI's API errors out, the route must fail gracefully with JSON,
    not a raw 500 traceback -- this is what lets the client show a retry
    state instead of freezing. 502 (not a bare 500) and error_category
    "upstream_service_error" let the frontend tell this apart from a
    timeout or an invalid-recording failure -- part of the reliability
    migration's error-category requirement.
    """
    client = _logged_in_client(app_client, make_user)

    with patch.object(
        app_module.client.audio.transcriptions,
        "create",
        side_effect=RuntimeError("upstream timeout"),
    ):
        resp = client.post(
            "/api/matching-game/transcribe",
            data={"audio": (io.BytesIO(b"fake-audio-bytes"), "match-response.webm")},
            content_type="multipart/form-data",
        )

    assert resp.status_code == 502
    body = resp.get_json()
    assert body["success"] is False
    assert body["error_category"] == "upstream_service_error"
    assert "error" in body


def test_other_voice_activities_share_the_same_transcribe_contract(app_client, make_user):
    """Every voice-enabled activity's transcribe route should behave like
    Activity 1's: same auth requirement, same 400-on-missing-audio shape,
    same 200-with-text success shape. A route that silently diverges here
    (different field name, different JSON keys, no login_required) is
    exactly the kind of inconsistency that broke the non-Activity-1 games.
    """
    client = _logged_in_client(app_client, make_user)

    for route in TRANSCRIBE_ROUTES:
        resp = client.post(route, data={})
        assert resp.status_code == 400, f"{route} did not 400 on missing audio"
        body = resp.get_json()
        assert body["success"] is False, f"{route} response missing success=False"

    for route in TRANSCRIBE_ROUTES:
        with patch.object(
            app_module.client.audio.transcriptions,
            "create",
            return_value=_fake_transcript("a red one"),
        ):
            resp = client.post(
                route,
                data={"audio": (io.BytesIO(b"fake-audio-bytes"), "clip.webm")},
                content_type="multipart/form-data",
            )
        assert resp.status_code == 200, f"{route} did not return 200 on success"
        body = resp.get_json()
        assert body["success"] is True
        assert body["text"] == "a red one"


def test_speech_harness_hidden_when_debug_off(app_client):
    """The mocked-event speech state-machine diagnostic (/debug/speech-harness)
    must never be reachable unless app.config["DEBUG"] is explicitly true --
    it's a development tool, not something that should ship to production.
    """
    assert app_module.app.config["DEBUG"] is False
    resp = app_client.get("/debug/speech-harness")
    assert resp.status_code == 404


def test_speech_harness_reachable_when_debug_on(app_client):
    app_module.app.config["DEBUG"] = True
    try:
        resp = app_client.get("/debug/speech-harness")
        assert resp.status_code == 200
        assert b"speech-state-machine-debug.js" in resp.data
    finally:
        app_module.app.config["DEBUG"] = False
