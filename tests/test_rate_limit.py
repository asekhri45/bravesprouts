"""Tests for the signup rate limit (~3/minute, ~10/hour) added to /signup
using the project's existing Flask-Limiter instance -- no new rate-limiting
system was introduced.
"""
import app as app_module
from conftest import VALID_PASSWORD


def test_signup_route_has_both_limits_registered():
    """Static check that both the burst (per-minute) and sustained
    (per-hour) limits are attached to the signup view, via Flask-Limiter's
    own limit_manager registry (flask_limiter._manager.LimitManager).
    """
    decorated = app_module.limiter.limit_manager._decorated_limits.get("app.signup.signup", [])
    providers = {entry.limit_provider for entry in decorated}
    assert "3 per minute" in providers
    assert "10 per hour" in providers


def test_signup_trips_per_minute_limit_after_three_requests(rate_limited_client):
    for i in range(3):
        resp = rate_limited_client.post("/signup", data={
            "email": f"burst{i}@example.test",
            "password": VALID_PASSWORD,
            "terms_check": "on",
        })
        assert resp.status_code == 302, f"request {i} should have succeeded, got {resp.status_code}"

    resp = rate_limited_client.post("/signup", data={
        "email": "burst-fourth@example.test",
        "password": VALID_PASSWORD,
        "terms_check": "on",
    })
    assert resp.status_code == 429


def test_signup_limit_is_per_ip_not_global(rate_limited_client):
    """Sanity check that the limiter key function is IP-based (get_remote_address),
    not a global counter -- confirmed via the registered key_function.
    """
    decorated = app_module.limiter.limit_manager._decorated_limits.get("app.signup.signup", [])
    for entry in decorated:
        assert entry.key_function.__name__ == "get_remote_address"
