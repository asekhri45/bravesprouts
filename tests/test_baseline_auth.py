"""Baseline tests for current authentication behavior (login, password
hashing, session creation, dashboard auth gate, duplicate email, PIN
string/leading-zero handling) -- captured before the two-step signup
rewrite, to prove the rewrite didn't silently change any of this.
"""
from werkzeug.security import check_password_hash

from conftest import VALID_PASSWORD, login_as_user


def test_password_is_hashed_not_stored_plaintext(app_client, make_user):
    user_id = make_user(email="hash@example.test")
    import app as app_module
    conn = app_module.get_db_connection()
    row = conn.execute("SELECT password FROM users WHERE user_id = ?", (user_id,)).fetchone()
    conn.close()
    assert row["password"] != VALID_PASSWORD
    assert check_password_hash(row["password"], VALID_PASSWORD)


def test_login_with_correct_credentials_succeeds(app_client, make_user):
    make_user(email="gooduser@example.test")
    resp = app_client.post("/login", data={
        "email": "gooduser@example.test",
        "password": VALID_PASSWORD,
    })
    assert resp.status_code == 302
    assert resp.headers["Location"] == "/dashboard"


def test_login_sets_session_correctly(app_client, make_user):
    user_id = make_user(email="sessioncheck@example.test", parent_name="Sess Test")
    app_client.post("/login", data={
        "email": "sessioncheck@example.test",
        "password": VALID_PASSWORD,
    })
    with app_client.session_transaction() as sess:
        assert sess["user_id"] == user_id
        assert sess["parent_name"] == "Sess Test"
        assert sess["parent_setup_complete"] is True


def test_login_with_wrong_password_fails(app_client, make_user):
    make_user(email="wrongpw@example.test")
    resp = app_client.post("/login", data={
        "email": "wrongpw@example.test",
        "password": "not-the-right-password",
    })
    assert resp.status_code == 200
    assert b"Incorrect email or password" in resp.data


def test_login_with_unknown_email_fails_generically(app_client):
    resp = app_client.post("/login", data={
        "email": "nobody@example.test",
        "password": "whatever123!",
    })
    assert resp.status_code == 200
    assert b"Incorrect email or password" in resp.data


def test_dashboard_requires_login(app_client):
    resp = app_client.get("/dashboard")
    assert resp.status_code == 302
    assert resp.headers["Location"] == "/login"


def test_dashboard_reachable_when_logged_in_and_complete(app_client, make_user):
    user_id = make_user(email="dashuser@example.test")
    login_as_user(app_client, user_id, parent_setup_complete=True)
    resp = app_client.get("/dashboard")
    assert resp.status_code == 200


def test_signup_rejects_duplicate_email(app_client, make_user):
    make_user(email="dupe@example.test")
    resp = app_client.post("/signup", data={
        "email": "dupe@example.test",
        "password": "AnotherPass1!",
        "terms_check": "on",
    })
    assert resp.status_code == 200
    assert b"already exists" in resp.data


def test_parent_pin_stored_and_compared_as_string(app_client, make_user):
    """A PIN beginning with zero must survive round-trip as a literal string."""
    import app as app_module
    user_id = make_user(email="leadingzero@example.test", parent_pin="0492")
    conn = app_module.get_db_connection()
    row = conn.execute("SELECT parent_pin FROM users WHERE user_id = ?", (user_id,)).fetchone()
    conn.close()
    assert row["parent_pin"] == "0492"
    assert isinstance(row["parent_pin"], str)


def test_parent_pin_gate_accepts_leading_zero_pin(app_client, make_user):
    user_id = make_user(email="pingatetest@example.test", parent_pin="0123")
    login_as_user(app_client, user_id, parent_setup_complete=True)
    resp = app_client.post("/parent-pin", data={"parent_pin": "0123"})
    assert resp.status_code == 302
    assert resp.headers["Location"] == "/dashboard"
