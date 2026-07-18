"""Shared pytest fixtures for the bravesprouts test suite.

Every test in this suite runs against a throwaway SQLite file created under
pytest's tmp_path — app.db (the production database) is never opened,
written to, or deleted by any fixture here.
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Must be set before `import app`, since app.py reads these at module load time.
os.environ.setdefault("FLASK_ENV", "testing")
os.environ["SECRET_KEY"] = "test-secret-key-not-for-production"
os.environ["ADMIN_EMAIL"] = "admin@example.test"
os.environ["ADMIN_PASSWORD"] = "test-admin-password"
os.environ.setdefault("OPENAI_API_KEY", "test-openai-key")
os.environ.setdefault("ELEVENLABS_API_KEY", "test-elevenlabs-key")

import pytest
from werkzeug.security import generate_password_hash

import app as app_module
import init_db as init_db_module

VALID_PASSWORD = "StrongPass1!"


@pytest.fixture
def temp_db(tmp_path, monkeypatch):
    """Point both app.py and init_db.py at a fresh temp SQLite file, then initialize it."""
    db_path = str(tmp_path / "test_app.db")
    monkeypatch.setattr(app_module, "DATABASE", db_path)
    monkeypatch.setattr(init_db_module, "DATABASE", db_path)
    init_db_module.init_db()
    # Mirror production: app.py's own boot-time migrators add columns
    # (login_count, has_seen_tour, feedback_prompt_dismissed_at, created_at,
    # parent_setup_complete) the first time a real request touches them. Run
    # them now so a fresh temp DB matches what app.db actually looks like in
    # production, post-migration.
    app_module.ensure_feedback_tables()
    app_module.ensure_parent_setup_column()
    return db_path


@pytest.fixture
def app_client(temp_db):
    """Flask test client with CSRF and rate limiting disabled, for general-behavior tests.

    Flask-Limiter caches `enabled` as a plain attribute at extension-init
    time (see flask_limiter/_extension.py: `self.enabled = config.setdefault(...)`
    runs once, during `Limiter(app=app)`), so setting
    app.config["RATELIMIT_ENABLED"] after import has no effect -- the
    attribute itself must be flipped directly.
    """
    app_module.app.config["TESTING"] = True
    app_module.app.config["WTF_CSRF_ENABLED"] = False
    app_module.limiter.enabled = False
    with app_module.app.test_client() as client:
        yield client
    app_module.limiter.enabled = True


@pytest.fixture
def csrf_client(temp_db):
    """Client with real CSRF validation enabled, rate limiting disabled.

    Used only by CSRF-specific tests -- everything else uses app_client,
    which disables CSRF so form-behavior tests don't need to carry a token.
    """
    app_module.app.config["TESTING"] = True
    app_module.app.config["WTF_CSRF_ENABLED"] = True
    app_module.limiter.enabled = False
    with app_module.app.test_client() as client:
        yield client
    app_module.limiter.enabled = True
    app_module.app.config["WTF_CSRF_ENABLED"] = False


@pytest.fixture
def rate_limited_client(temp_db):
    """Client with real Flask-Limiter enforcement enabled, CSRF disabled."""
    app_module.app.config["TESTING"] = True
    app_module.app.config["WTF_CSRF_ENABLED"] = False
    app_module.limiter.enabled = True
    app_module.limiter.reset()
    with app_module.app.test_client() as client:
        yield client
    app_module.limiter.reset()
    app_module.limiter.enabled = False


def extract_csrf_token(html_bytes):
    import re
    match = re.search(rb'name="csrf_token"\s+value="([^"]+)"', html_bytes)
    assert match, "no csrf_token hidden input found in rendered page"
    return match.group(1).decode()


@pytest.fixture
def make_user(temp_db):
    """Factory fixture: insert a user row directly, bypassing the signup route."""

    def _make(**overrides):
        fields = {
            "email": "parent@example.test",
            "password": generate_password_hash(VALID_PASSWORD),
            "parent_name": "Test Parent",
            "child_name": None,
            "child_dob": None,
            "child_age": None,
            "parent_pin": "1234",
            "terms_check": 1,
            # Defaults to a normal, fully-set-up account -- pass
            # parent_setup_complete=0 to simulate a Step-1-only account.
            "parent_setup_complete": 1,
        }
        fields.update(overrides)

        conn = app_module.get_db_connection()
        cur = conn.cursor()
        cur.execute(
            """
            INSERT INTO users (
                email, password, parent_name, child_name, child_dob,
                child_age, parent_pin, terms_check, parent_setup_complete, created_at
            )
            VALUES (
                :email, :password, :parent_name, :child_name, :child_dob,
                :child_age, :parent_pin, :terms_check, :parent_setup_complete, CURRENT_TIMESTAMP
            )
            """,
            fields,
        )
        user_id = cur.lastrowid
        conn.commit()
        conn.close()
        return user_id

    return _make


def login_as_admin(client):
    with client.session_transaction() as sess:
        sess["is_admin"] = True


def login_as_user(client, user_id, parent_name="Test Parent", parent_setup_complete=True):
    """Simulate an authenticated session, as login()/signup() would set it up.

    Pass parent_setup_complete=None to simulate an older session that
    predates this flag entirely, exercising the DB-fallback read path in
    get_or_load_parent_setup_complete() instead of trusting a cached value.
    """
    with client.session_transaction() as sess:
        sess["user_id"] = user_id
        sess["parent_name"] = parent_name
        sess["child_name"] = ""
        sess["profile_icon"] = "profileicon.png"
        if parent_setup_complete is not None:
            sess["parent_setup_complete"] = parent_setup_complete
