"""Tests for the homepage's (and shared public navbar's) unconditional
public CTA, the curated activities list, and the dedicated homepage-carousel
image mapping.
"""
import app as app_module
from conftest import login_as_user

# Public marketing pages must never show dashboard-navigation language,
# regardless of session state -- signup()/login() already redirect an
# authenticated visitor to the right place after they click.
FORBIDDEN_CTA_PHRASES = [
    b"Back to Dashboard",
    b"Go to Dashboard",
    b"Open Dashboard",
    b"Finish Parent Setup",
]

PUBLIC_PAGES = ["/", "/parent-resources", "/our-story", "/acknowledgments2"]


def _assert_public_cta(resp):
    assert resp.status_code == 200
    assert b"Create Free Parent Account" in resp.data
    assert b"Log in" in resp.data or b"Login" in resp.data
    for phrase in FORBIDDEN_CTA_PHRASES:
        assert phrase not in resp.data


def test_homepage_cta_logged_out(app_client):
    _assert_public_cta(app_client.get("/"))


def test_homepage_cta_unchanged_when_complete_account_logged_in(app_client, make_user):
    user_id = make_user(email="ctacomplete@example.test")
    login_as_user(app_client, user_id, parent_setup_complete=True)
    _assert_public_cta(app_client.get("/"))


def test_homepage_cta_unchanged_when_incomplete_account_logged_in(app_client, make_user):
    user_id = make_user(email="ctaincomplete@example.test", parent_setup_complete=0, parent_name="", parent_pin=None)
    login_as_user(app_client, user_id, parent_setup_complete=False)
    _assert_public_cta(app_client.get("/"))


def test_all_four_public_pages_show_same_cta_logged_out(app_client):
    for path in PUBLIC_PAGES:
        _assert_public_cta(app_client.get(path))


def test_all_four_public_pages_show_same_cta_when_logged_in_complete(app_client, make_user):
    user_id = make_user(email="navctacomplete@example.test")
    login_as_user(app_client, user_id, parent_setup_complete=True)
    for path in PUBLIC_PAGES:
        _assert_public_cta(app_client.get(path))


def test_all_four_public_pages_show_same_cta_when_logged_in_incomplete(app_client, make_user):
    user_id = make_user(email="navctaincomplete@example.test", parent_setup_complete=0, parent_name="", parent_pin=None)
    login_as_user(app_client, user_id, parent_setup_complete=False)
    for path in PUBLIC_PAGES:
        _assert_public_cta(app_client.get(path))


def test_homepage_does_not_redirect_logged_in_users(app_client, make_user):
    """Public homepage content must remain viewable while logged in."""
    user_id = make_user(email="staysonhome@example.test")
    login_as_user(app_client, user_id, parent_setup_complete=True)
    resp = app_client.get("/")
    assert resp.status_code == 200  # not a redirect


def test_signup_and_login_routes_still_redirect_authenticated_visitors(app_client, make_user):
    """The public CTA text never changes, but clicking through must still
    route an already-authenticated visitor correctly -- this is handled by
    signup()/login() themselves, already covered by
    tests/test_two_step_signup.py::TestSetupResume, and reconfirmed here in
    the context of the unconditional public CTA.
    """
    complete_id = make_user(email="clickthroughcomplete@example.test")
    login_as_user(app_client, complete_id, parent_setup_complete=True)
    resp = app_client.get("/login")
    assert resp.status_code == 302
    assert resp.headers["Location"] == "/dashboard"


def test_curated_activities_only_includes_approved_names(temp_db):
    conn = app_module.get_db_connection()
    cur = conn.cursor()
    cur.execute("INSERT INTO scene (scene_name) VALUES ('s')")
    scene_id = cur.lastrowid

    # An approved, active, playable activity.
    cur.execute(
        "INSERT INTO activity (scene_id, activity_name, activity_order, is_active, template_file, description, character_active) "
        "VALUES (?, 'match_cards', 1, 1, 'match_cards.html', 'Find matching pairs with Star.', 'Star')",
        (scene_id,),
    )
    # An approved name, but inactive -- must be excluded.
    cur.execute(
        "INSERT INTO activity (scene_id, activity_name, activity_order, is_active, template_file) "
        "VALUES (?, 'guessing_game', 2, 0, 'guessing_game.html')",
        (scene_id,),
    )
    # Not in the curated allowlist at all -- must be excluded regardless of state.
    cur.execute(
        "INSERT INTO activity (scene_id, activity_name, activity_order, is_active, template_file) "
        "VALUES (?, 'toy_sorting_game', 3, 1, 'toy_sorting_game.html')",
        (scene_id,),
    )
    # Approved + active, but no real template (Coming Soon placeholder) -- excluded.
    cur.execute(
        "INSERT INTO activity (scene_id, activity_name, activity_order, is_active, template_file) "
        "VALUES (?, 'mystery_animal', 4, 1, NULL)",
        (scene_id,),
    )
    conn.commit()
    conn.close()

    activities = app_module.get_homepage_activities()
    names = {a["name"] for a in activities}

    assert names == {"match_cards"}
    assert activities[0]["skill"] == "Responding & taking turns"
    assert activities[0]["description"] == "Find matching pairs with Star."
    assert activities[0]["image"] == "match_cards_home_optimized.webp"


def test_every_curated_activity_maps_to_a_dedicated_carousel_image():
    """Every entry must point at a *_home_optimized.webp file -- a cropped,
    resized, compressed derivative of the real gameplay screenshot, explicitly
    mapped (not derived from the DB activity_name string) -- and that file
    must actually exist on disk.
    """
    import os

    assert set(app_module.HOMEPAGE_ACTIVITY_IMAGES) == set(app_module.HOMEPAGE_ACTIVITY_SKILLS)

    static_images_dir = os.path.join(os.path.dirname(app_module.__file__), "static", "images")
    for name, filename in app_module.HOMEPAGE_ACTIVITY_IMAGES.items():
        assert filename.endswith("_home_optimized.webp"), f"{name} -> {filename} isn't a dedicated optimized carousel asset"
        full_path = os.path.join(static_images_dir, filename)
        assert os.path.isfile(full_path), f"missing dedicated carousel asset: {full_path}"
        # Keep the homepage lightweight -- the optimized derivative must stay
        # well under the multi-megabyte size of the source screenshot.
        assert os.path.getsize(full_path) < 210 * 1024, f"{filename} is too large for the homepage"


def test_dedicated_carousel_images_do_not_overwrite_originals():
    """The *_home_optimized.webp derivatives must be separate from -- not
    renamed copies replacing -- the original *_home_img.png gameplay
    screenshots or the dashboard's journey-card icons.
    """
    import os

    static_images_dir = os.path.join(os.path.dirname(app_module.__file__), "static", "images")
    for name in app_module.HOMEPAGE_ACTIVITY_SKILLS:
        original_path = os.path.join(static_images_dir, f"{name}.png")
        assert os.path.isfile(original_path), f"original image missing/renamed: {original_path}"

        screenshot_path = os.path.join(static_images_dir, f"{name}_home_img.png")
        assert os.path.isfile(screenshot_path), f"source gameplay screenshot missing/renamed: {screenshot_path}"
