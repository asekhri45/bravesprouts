"""Regression tests for the admin_required guard on /admin/user-overview and /admin/feedback.

Both routes previously had no access control at all. These tests prove:
  - a logged-out visitor is redirected to /admin/login
  - an ordinary authenticated (non-admin) user is redirected to /admin/login
  - a valid admin session can reach the page (200 OK)
"""
from conftest import login_as_admin, login_as_user

ADMIN_ROUTES = ["/admin/user-overview", "/admin/feedback"]


def test_admin_required_decorator_blocks_non_admin_session(app_client):
    with app_client.session_transaction() as sess:
        sess["is_admin"] = False
    resp = app_client.get("/admin/user-overview")
    assert resp.status_code in (301, 302)
    assert resp.headers["Location"].endswith("/admin/login")


def test_admin_required_decorator_allows_admin_session(app_client):
    login_as_admin(app_client)
    resp = app_client.get("/admin/user-overview")
    assert resp.status_code == 200


def test_logged_out_visitor_cannot_access_user_overview(app_client):
    resp = app_client.get("/admin/user-overview")
    assert resp.status_code in (301, 302)
    assert resp.headers["Location"].endswith("/admin/login")


def test_logged_out_visitor_cannot_access_feedback(app_client):
    resp = app_client.get("/admin/feedback")
    assert resp.status_code in (301, 302)
    assert resp.headers["Location"].endswith("/admin/login")


def test_ordinary_user_cannot_access_user_overview(app_client, make_user):
    user_id = make_user(email="ordinary@example.test")
    login_as_user(app_client, user_id)
    resp = app_client.get("/admin/user-overview")
    assert resp.status_code in (301, 302)
    assert resp.headers["Location"].endswith("/admin/login")


def test_ordinary_user_cannot_access_feedback(app_client, make_user):
    user_id = make_user(email="ordinary2@example.test")
    login_as_user(app_client, user_id)
    resp = app_client.get("/admin/feedback")
    assert resp.status_code in (301, 302)
    assert resp.headers["Location"].endswith("/admin/login")


def test_admin_can_access_user_overview(app_client):
    login_as_admin(app_client)
    resp = app_client.get("/admin/user-overview")
    assert resp.status_code == 200
    assert b"user" in resp.data.lower() or b"total" in resp.data.lower()


def test_admin_can_access_feedback(app_client):
    login_as_admin(app_client)
    resp = app_client.get("/admin/feedback")
    assert resp.status_code == 200


def test_admin_session_survives_across_both_routes(app_client):
    """A single admin login should grant access to every admin route, not just one."""
    login_as_admin(app_client)
    for route in ADMIN_ROUTES:
        resp = app_client.get(route)
        assert resp.status_code == 200, f"admin session was rejected on {route}"
