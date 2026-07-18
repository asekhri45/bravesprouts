"""Tests for the privacy-safe analytics wiring: confirms each page ships
the expected data-analytics-event hooks and, critically, that no page ever
embeds PII (email, password, PIN, name, child info) inside an analytics
attribute payload.
"""
import re

import app as app_module
from conftest import VALID_PASSWORD, login_as_user

PII_PATTERNS = ["email", "password", "pin", "parent_name", "child_name", "dob"]


def _analytics_props(html_bytes):
    """Extract every data-analytics-props JSON blob from a page's HTML."""
    return re.findall(rb'data-analytics-props=\'([^\']*)\'', html_bytes)


def test_homepage_has_pageview_and_cta_hooks(app_client):
    resp = app_client.get("/")
    assert b'data-analytics-event="homepage_view"' in resp.data
    assert b'data-analytics-event="hero_cta_click"' in resp.data
    # activity_carousel_view/activity_preview_started are wired in JS
    # (IntersectionObserver-gated), not as a static page-load attribute --
    # confirm it's NOT also present as a stray attribute, which would
    # double-fire the event immediately on every page load.
    assert b'data-analytics-event="activity_carousel_view"' not in resp.data


def test_signup_page_has_expected_hooks(app_client):
    resp = app_client.get("/signup")
    assert b'data-analytics-event="signup_page_view"' in resp.data
    assert b'data-analytics-event="signup_submit_attempt"' in resp.data


def test_parent_setup_page_has_pageview_hook(app_client, make_user):
    user_id = make_user(email="analyticssetup@example.test", parent_setup_complete=0, parent_name="", parent_pin=None)
    login_as_user(app_client, user_id, parent_setup_complete=False)
    resp = app_client.get("/parent-setup")
    assert b'data-analytics-event="parent_setup_started"' in resp.data
    # parent_setup_completed must NOT be wired as a click-bound attribute on
    # this page -- it only fires after Step 2's server-side UPDATE commits
    # (see test_parent_setup_completed_only_fires_after_server_success).
    assert b'data-analytics-event="parent_setup_completed"' not in resp.data


def test_parent_setup_completed_only_fires_after_server_success(app_client, make_user):
    """parent_setup_completed must not fire merely on submit -- it should
    only become detectable once the server has actually committed
    parent_setup_complete = 1 and redirected with the one-time setup=1 flag.
    """
    user_id = make_user(email="analyticscompleted@example.test", parent_setup_complete=0, parent_name="", parent_pin=None)
    login_as_user(app_client, user_id, parent_setup_complete=False)

    # A failed submission (invalid PIN) must not carry the setup=1 flag,
    # since the server never committed parent_setup_complete = 1.
    failed = app_client.post("/parent-setup", data={"parent_name": "X", "parent_pin": "12"})
    assert failed.status_code == 200

    conn = app_module.get_db_connection()
    row = conn.execute(
        "SELECT parent_setup_complete FROM users WHERE user_id = ?", (user_id,)
    ).fetchone()
    conn.close()
    assert row["parent_setup_complete"] == 0

    # A successful submission redirects with setup=1 -- and only then does
    # dashboard_layout.html's inline script fire the event.
    ok = app_client.post("/parent-setup", data={"parent_name": "Real Parent", "parent_pin": "4821"})
    assert ok.status_code == 302
    assert ok.headers["Location"] == "/dashboard?setup=1"

    conn = app_module.get_db_connection()
    row = conn.execute(
        "SELECT parent_setup_complete FROM users WHERE user_id = ?", (user_id,)
    ).fetchone()
    conn.close()
    assert row["parent_setup_complete"] == 1

    dashboard_resp = app_client.get("/dashboard?setup=1")
    assert dashboard_resp.status_code == 200
    assert b'"setup=1"' in dashboard_resp.data
    assert b"parent_setup_completed" in dashboard_resp.data


def test_signup_success_redirects_with_new_flag_for_account_created(app_client):
    resp = app_client.post("/signup", data={
        "email": "trackcreated@example.test",
        "password": VALID_PASSWORD,
        "terms_check": "on",
    })
    assert resp.status_code == 302
    assert resp.headers["Location"] == "/parent-setup?new=1"


def test_no_analytics_props_anywhere_contain_pii_keywords(app_client, make_user):
    """Static scan: every data-analytics-props blob on every page we can
    reach logged-out must not contain obvious PII field names.
    """
    for path in ("/", "/signup"):
        resp = app_client.get(path)
        for blob in _analytics_props(resp.data):
            lowered = blob.lower()
            for keyword in PII_PATTERNS:
                assert keyword.encode() not in lowered, (
                    f"{path} has a data-analytics-props blob mentioning '{keyword}': {blob}"
                )


def test_first_activity_started_flag_set_on_first_open_only(app_client, make_user):
    """open_activity() should mark is_first_activity True only the very
    first time a given user opens any activity.
    """
    user_id = make_user(email="firstactivity@example.test", child_name="Ari")
    conn = app_module.get_db_connection()
    cur = conn.cursor()
    cur.execute("INSERT INTO scene (scene_name) VALUES ('s')")
    scene_id = cur.lastrowid
    cur.execute(
        "INSERT INTO activity (scene_id, activity_name, activity_order, is_active, template_file) "
        "VALUES (?, 'a1', 1, 1, 'match_cards.html')",
        (scene_id,),
    )
    activity_id = cur.lastrowid
    cur.execute(
        "INSERT INTO progress (user_id, activity_id, is_unlocked) VALUES (?, ?, 1)",
        (user_id, activity_id),
    )
    conn.commit()
    conn.close()

    login_as_user(app_client, user_id, parent_setup_complete=True)

    first_resp = app_client.get(f"/activity/{activity_id}")
    assert first_resp.status_code == 200
    assert b"first_activity_started" in first_resp.data

    second_resp = app_client.get(f"/activity/{activity_id}")
    assert second_resp.status_code == 200
    assert b"first_activity_started" not in second_resp.data
