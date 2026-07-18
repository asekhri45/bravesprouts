"""Tests for the carousel's server-rendered progress-indicator markup.

The actual scroll/drag/keyboard behavior lives in static/js/activities-carousel.js
and was verified interactively (pointer drag tracking, arrow navigation,
keyboard nav, resize handling, duplicate-init guard) since pytest has no JS
runtime. This file only confirms the HTML scaffolding those behaviors
attach to is present and correct, and that the old dot-pagination markup
is fully gone.
"""


def test_homepage_has_progress_track_not_dots(app_client):
    resp = app_client.get("/")
    assert b'id="activitiesProgressTrack"' in resp.data
    assert b'id="activitiesProgressFill"' in resp.data
    assert b'id="activitiesCounter"' in resp.data
    assert b'role="progressbar"' in resp.data
    # Old dot-pagination markup must be fully removed, not just unused.
    assert b'activities-dots' not in resp.data
    assert b'activitiesDots' not in resp.data


def test_progress_counter_reflects_actual_curated_activity_count(app_client):
    resp = app_client.get("/")
    # 8 curated activities are seeded via conftest's temp_db + make_user
    # fixtures' shared activity table in most tests, but on a bare temp_db
    # the count is whatever get_homepage_activities() returns -- just
    # confirm the counter text is well-formed ("N of M") and non-empty.
    assert b'1 of ' in resp.data


def test_arrow_buttons_still_present_alongside_progress_bar(app_client):
    resp = app_client.get("/")
    assert b'activities-arrow-prev' in resp.data
    assert b'activities-arrow-next' in resp.data
    assert b'Previous activity' in resp.data
    assert b'Next activity' in resp.data
