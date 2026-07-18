"""Tests for the new two-step signup flow: Step 1 (email/password/terms)
creates an incomplete account; Step 2 (/parent-setup) completes it; the
centralized guard blocks incomplete accounts from every normal route;
setup resumes correctly across logout/login.
"""
import app as app_module
from conftest import VALID_PASSWORD, login_as_user

PROTECTED_ROUTES = [
    "/dashboard",
    "/settings",
    "/lessons",
    "/characters",
    "/acknowledgments",
]


def _seed_activity(user_id=None):
    """init_db.py only creates the activity/scene schema; real rows are
    seeded separately in production. Insert one so activity-route tests
    have something real to request (and, optionally, unlock it for a user).
    """
    conn = app_module.get_db_connection()
    cur = conn.cursor()
    cur.execute("INSERT INTO scene (scene_name) VALUES ('test_scene')")
    scene_id = cur.lastrowid
    cur.execute(
        "INSERT INTO activity (scene_id, activity_name, activity_order, is_active, template_file) "
        "VALUES (?, 'test_activity', 1, 1, 'match_cards.html')",
        (scene_id,),
    )
    activity_id = cur.lastrowid
    if user_id is not None:
        cur.execute(
            "INSERT INTO progress (user_id, activity_id, is_unlocked) VALUES (?, ?, 1)",
            (user_id, activity_id),
        )
    conn.commit()
    conn.close()
    return activity_id


def _signup_step1(client, email="newparent@example.test", password=VALID_PASSWORD, terms="on"):
    data = {"email": email, "password": password}
    if terms is not None:
        data["terms_check"] = terms
    return client.post("/signup", data=data)


class TestStep1:
    def test_step1_creates_incomplete_account(self, app_client):
        resp = _signup_step1(app_client)
        assert resp.status_code == 302
        # ?new=1 lets the client fire an account_created analytics event
        # exactly once; unrelated redirects to /parent-setup (guards,
        # login-resume) don't carry it.
        assert resp.headers["Location"] == "/parent-setup?new=1"

        conn = app_module.get_db_connection()
        row = conn.execute(
            "SELECT parent_setup_complete, parent_name, parent_pin, terms_check FROM users WHERE email = ?",
            ("newparent@example.test",),
        ).fetchone()
        conn.close()

        assert row is not None
        assert row["parent_setup_complete"] == 0
        assert row["parent_name"] == ""
        assert row["parent_pin"] is None
        assert row["terms_check"] == 1

    def test_step1_rejects_missing_terms(self, app_client):
        resp = _signup_step1(app_client, email="noterms@example.test", terms=None)
        assert resp.status_code == 200
        assert b"Terms of Use" in resp.data

        conn = app_module.get_db_connection()
        row = conn.execute("SELECT * FROM users WHERE email = ?", ("noterms@example.test",)).fetchone()
        conn.close()
        assert row is None  # no account created without terms acceptance

    def test_step1_rejects_invalid_email_format(self, app_client):
        resp = app_client.post("/signup", data={
            "email": "not-an-email",
            "password": VALID_PASSWORD,
            "terms_check": "on",
        })
        assert resp.status_code == 200
        assert b"valid email" in resp.data

    def test_step1_rejects_weak_password(self, app_client):
        resp = app_client.post("/signup", data={
            "email": "weakpw@example.test",
            "password": "short",
            "terms_check": "on",
        })
        assert resp.status_code == 200
        assert b"8 characters" in resp.data

    def test_step1_no_confirm_password_field_required(self, app_client):
        """The rewritten backend has no confirm_password concept at all."""
        resp = _signup_step1(app_client, email="noconfirm@example.test")
        assert resp.status_code == 302  # succeeds without ever sending confirm_password


class TestStep2:
    def test_step2_completes_account(self, app_client):
        _signup_step1(app_client, email="stepper@example.test")
        resp = app_client.post("/parent-setup", data={
            "parent_name": "Jamie Parent",
            "parent_pin": "4821",
        })
        assert resp.status_code == 302
        assert resp.headers["Location"] == "/dashboard?setup=1"

        conn = app_module.get_db_connection()
        row = conn.execute(
            "SELECT parent_setup_complete, parent_name, parent_pin FROM users WHERE email = ?",
            ("stepper@example.test",),
        ).fetchone()
        conn.close()
        assert row["parent_setup_complete"] == 1
        assert row["parent_name"] == "Jamie Parent"
        assert row["parent_pin"] == "4821"

    def test_step2_rejects_invalid_pin(self, app_client):
        _signup_step1(app_client, email="badpin@example.test")
        resp = app_client.post("/parent-setup", data={
            "parent_name": "Someone",
            "parent_pin": "12a4",
        })
        assert resp.status_code == 200
        assert b"4 digits" in resp.data

    def test_step2_accepts_pin_beginning_with_zero(self, app_client):
        _signup_step1(app_client, email="zeropin@example.test")
        resp = app_client.post("/parent-setup", data={
            "parent_name": "Someone",
            "parent_pin": "0492",
        })
        assert resp.status_code == 302
        conn = app_module.get_db_connection()
        row = conn.execute(
            "SELECT parent_pin FROM users WHERE email = ?", ("zeropin@example.test",)
        ).fetchone()
        conn.close()
        assert row["parent_pin"] == "0492"

    def test_step2_rejects_missing_parent_name(self, app_client):
        _signup_step1(app_client, email="noname@example.test")
        resp = app_client.post("/parent-setup", data={
            "parent_name": "",
            "parent_pin": "1234",
        })
        assert resp.status_code == 200
        assert b"Parent name is required" in resp.data


class TestGuardBlocksIncompleteAccounts:
    def test_incomplete_account_cannot_reach_protected_routes(self, app_client, make_user):
        user_id = make_user(email="incomplete@example.test", parent_setup_complete=0, parent_name="", parent_pin=None)
        login_as_user(app_client, user_id, parent_setup_complete=False)

        for route in PROTECTED_ROUTES:
            resp = app_client.get(route)
            assert resp.status_code == 302, f"{route} should redirect an incomplete account"
            assert resp.headers["Location"] == "/parent-setup", f"{route} redirected somewhere unexpected"

    def test_incomplete_account_can_reach_parent_setup(self, app_client, make_user):
        user_id = make_user(email="incomplete2@example.test", parent_setup_complete=0, parent_name="", parent_pin=None)
        login_as_user(app_client, user_id, parent_setup_complete=False)
        resp = app_client.get("/parent-setup")
        assert resp.status_code == 200

    def test_incomplete_account_can_delete_account(self, app_client, make_user):
        user_id = make_user(email="incomplete3@example.test", parent_setup_complete=0, parent_name="", parent_pin=None)
        login_as_user(app_client, user_id, parent_setup_complete=False)
        resp = app_client.post("/delete-account")
        assert resp.status_code == 302
        assert resp.headers["Location"] == "/login"

    def test_incomplete_account_can_logout(self, app_client, make_user):
        user_id = make_user(email="incomplete4@example.test", parent_setup_complete=0, parent_name="", parent_pin=None)
        login_as_user(app_client, user_id, parent_setup_complete=False)
        resp = app_client.get("/logout")
        assert resp.status_code == 302

    def test_incomplete_account_cannot_reach_activity_route(self, app_client, make_user):
        activity_id = _seed_activity()
        user_id = make_user(email="incomplete5@example.test", parent_setup_complete=0, parent_name="", parent_pin=None)
        login_as_user(app_client, user_id, parent_setup_complete=False)
        resp = app_client.get(f"/activity/{activity_id}")
        assert resp.status_code == 302
        assert resp.headers["Location"] == "/parent-setup"

    def test_incomplete_account_cannot_reach_product_api_route(self, app_client, make_user):
        """Product/game API routes (e.g. /api/guessing-game-2/message) are
        @login_required like everything else, so the centralized guard
        covers them too -- the guard runs before the view body, so this
        blocks regardless of what the request body contains.
        """
        user_id = make_user(email="incomplete6@example.test", parent_setup_complete=0, parent_name="", parent_pin=None)
        login_as_user(app_client, user_id, parent_setup_complete=False)
        resp = app_client.post("/api/guessing-game-2/message", json={"message": "hi"})
        assert resp.status_code == 302
        assert resp.headers["Location"] == "/parent-setup"

    def test_incomplete_account_cannot_submit_feedback(self, app_client, make_user):
        user_id = make_user(email="incomplete7@example.test", parent_setup_complete=0, parent_name="", parent_pin=None)
        login_as_user(app_client, user_id, parent_setup_complete=False)
        resp = app_client.post("/submit-feedback", data={"what_child_enjoyed": "x"})
        assert resp.status_code == 302
        assert resp.headers["Location"] == "/parent-setup"

    def test_complete_account_can_reach_activity_route(self, app_client, make_user):
        # child_name must be set to a real value or open_activity() redirects
        # to dashboard for an unrelated, pre-existing reason (child-name
        # completion) -- not something this guard change should affect.
        user_id = make_user(email="completeactivity@example.test", child_name="Ari")
        activity_id = _seed_activity(user_id=user_id)
        login_as_user(app_client, user_id, parent_setup_complete=True)
        resp = app_client.get(f"/activity/{activity_id}")
        assert resp.status_code == 200

    def test_complete_account_unaffected_by_guard(self, app_client, make_user):
        """Existing/completed accounts must keep working exactly as before."""
        user_id = make_user(email="complete@example.test")  # parent_setup_complete=1 by default
        login_as_user(app_client, user_id, parent_setup_complete=True)
        for route in PROTECTED_ROUTES:
            resp = app_client.get(route)
            assert resp.status_code == 200, f"{route} should be reachable for a complete account"


class TestSetupResume:
    def test_login_after_step1_redirects_to_parent_setup(self, app_client):
        _signup_step1(app_client, email="resume@example.test")
        # Simulate leaving: clear session as logout would
        with app_client.session_transaction() as sess:
            sess.clear()

        resp = app_client.post("/login", data={
            "email": "resume@example.test",
            "password": VALID_PASSWORD,
        })
        assert resp.status_code == 302
        assert resp.headers["Location"] == "/parent-setup"

    def test_login_after_completed_setup_goes_to_dashboard(self, app_client):
        _signup_step1(app_client, email="resume2@example.test")
        app_client.post("/parent-setup", data={"parent_name": "Done Parent", "parent_pin": "5678"})
        with app_client.session_transaction() as sess:
            sess.clear()

        resp = app_client.post("/login", data={
            "email": "resume2@example.test",
            "password": VALID_PASSWORD,
        })
        assert resp.status_code == 302
        assert resp.headers["Location"] == "/dashboard"

    def test_get_signup_while_incomplete_redirects_to_parent_setup(self, app_client, make_user):
        user_id = make_user(email="incompletebrowse@example.test", parent_setup_complete=0, parent_name="", parent_pin=None)
        login_as_user(app_client, user_id, parent_setup_complete=False)
        resp = app_client.get("/signup")
        assert resp.status_code == 302
        assert resp.headers["Location"] == "/parent-setup"

    def test_get_login_while_complete_redirects_to_dashboard(self, app_client, make_user):
        user_id = make_user(email="alreadyin@example.test")
        login_as_user(app_client, user_id, parent_setup_complete=True)
        resp = app_client.get("/login")
        assert resp.status_code == 302
        assert resp.headers["Location"] == "/dashboard"


class TestGuardNeverDefaultsMissingFlagToComplete:
    def test_missing_session_flag_falls_back_to_db_and_blocks_incomplete_user(self, app_client, make_user):
        """Simulates an old session cookie created before parent_setup_complete
        existed in the session shape: the flag is absent entirely, not False.
        The guard must read the DB rather than assume completion.
        """
        user_id = make_user(email="oldsession@example.test", parent_setup_complete=0, parent_name="", parent_pin=None)
        login_as_user(app_client, user_id, parent_setup_complete=None)  # flag not set at all

        with app_client.session_transaction() as sess:
            assert "parent_setup_complete" not in sess

        resp = app_client.get("/dashboard")
        assert resp.status_code == 302
        assert resp.headers["Location"] == "/parent-setup"

    def test_missing_session_flag_falls_back_to_db_and_allows_complete_user(self, app_client, make_user):
        user_id = make_user(email="oldsession2@example.test")  # parent_setup_complete=1
        login_as_user(app_client, user_id, parent_setup_complete=None)

        resp = app_client.get("/dashboard")
        assert resp.status_code == 200

    def test_db_fallback_populates_session_after_first_check(self, app_client, make_user):
        user_id = make_user(email="oldsession3@example.test")
        login_as_user(app_client, user_id, parent_setup_complete=None)

        app_client.get("/dashboard")

        with app_client.session_transaction() as sess:
            assert sess["parent_setup_complete"] is True
