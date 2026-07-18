"""Tests for CSRF re-enablement on /login, /signup, and /parent-setup.

All three routes previously carried @csrf.exempt despite CSRFProtect being
configured globally. This suite proves: a request with a valid token
succeeds, a request with a missing/invalid token is rejected, and the
rejection renders a friendly page (not a bare Werkzeug 400).
"""
from conftest import VALID_PASSWORD, extract_csrf_token, login_as_user


def test_login_succeeds_with_valid_csrf_token(csrf_client, make_user):
    make_user(email="csrfok@example.test")
    page = csrf_client.get("/login")
    token = extract_csrf_token(page.data)

    resp = csrf_client.post("/login", data={
        "email": "csrfok@example.test",
        "password": VALID_PASSWORD,
        "csrf_token": token,
    })
    assert resp.status_code == 302
    assert resp.headers["Location"] == "/dashboard"


def test_login_rejected_with_missing_csrf_token(csrf_client, make_user):
    make_user(email="csrfmissing@example.test")
    resp = csrf_client.post("/login", data={
        "email": "csrfmissing@example.test",
        "password": VALID_PASSWORD,
    })
    assert resp.status_code == 400
    assert b"expired" in resp.data.lower()
    assert b"Traceback" not in resp.data  # not a raw debug/500 page


def test_login_rejected_with_invalid_csrf_token(csrf_client, make_user):
    make_user(email="csrfbad@example.test")
    resp = csrf_client.post("/login", data={
        "email": "csrfbad@example.test",
        "password": VALID_PASSWORD,
        "csrf_token": "not-a-real-token",
    })
    assert resp.status_code == 400
    assert b"expired" in resp.data.lower()


def test_signup_succeeds_with_valid_csrf_token(csrf_client):
    page = csrf_client.get("/signup")
    token = extract_csrf_token(page.data)

    resp = csrf_client.post("/signup", data={
        "email": "csrfsignup@example.test",
        "password": VALID_PASSWORD,
        "terms_check": "on",
        "csrf_token": token,
    })
    assert resp.status_code == 302
    assert resp.headers["Location"] == "/parent-setup?new=1"


def test_signup_rejected_with_missing_csrf_token(csrf_client):
    resp = csrf_client.post("/signup", data={
        "email": "csrfsignupmissing@example.test",
        "password": VALID_PASSWORD,
        "terms_check": "on",
    })
    assert resp.status_code == 400
    assert b"expired" in resp.data.lower()


def test_parent_setup_succeeds_with_valid_csrf_token(csrf_client, make_user):
    user_id = make_user(email="csrfsetup@example.test", parent_setup_complete=0, parent_name="", parent_pin=None)
    login_as_user(csrf_client, user_id, parent_setup_complete=False)

    page = csrf_client.get("/parent-setup")
    token = extract_csrf_token(page.data)

    resp = csrf_client.post("/parent-setup", data={
        "parent_name": "CSRF Parent",
        "parent_pin": "1357",
        "csrf_token": token,
    })
    assert resp.status_code == 302
    assert resp.headers["Location"] == "/dashboard?setup=1"


def test_parent_setup_rejected_with_missing_csrf_token(csrf_client, make_user):
    user_id = make_user(email="csrfsetupmissing@example.test", parent_setup_complete=0, parent_name="", parent_pin=None)
    login_as_user(csrf_client, user_id, parent_setup_complete=False)

    resp = csrf_client.post("/parent-setup", data={
        "parent_name": "CSRF Parent",
        "parent_pin": "1357",
    })
    assert resp.status_code == 400
    assert b"expired" in resp.data.lower()


def test_unrelated_exempt_routes_still_exempt(csrf_client):
    """Confirm this change did not touch any route outside login/signup/parent-setup.

    /admin/login was CSRF-exempt before this work and must remain so.
    """
    resp = csrf_client.post("/admin/login", data={
        "email": "admin@example.test",
        "password": "test-admin-password",
    })
    # No csrf_token sent at all -- if this route were no longer exempt, it
    # would 400. A redirect (valid creds) or a 200 (invalid creds) both
    # prove CSRF is not being enforced here, i.e. exemption is unchanged.
    assert resp.status_code in (200, 302)
