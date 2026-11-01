"""Tests for the public research page (/research) and its paper PDF."""
from conftest import login_as_user

PAPER_TITLE = b"Toward Parameter-Efficient and Trustworthy Transformers for Stress Detection in Reddit Posts"


def test_research_page_is_public(app_client):
    resp = app_client.get("/research")
    assert resp.status_code == 200
    assert PAPER_TITLE in resp.data
    assert b"Aarav Sekhri" in resp.data
    assert b"Dr. Bartosz Krawczyk" in resp.data
    assert b'href="/research/paper.pdf"' in resp.data
    assert b'href="/research/paper.pdf?download=1"' in resp.data


def test_research_page_works_when_logged_in(app_client, make_user):
    user_id = make_user(email="researchviewer@example.test")
    login_as_user(app_client, user_id, parent_setup_complete=True)
    assert app_client.get("/research").status_code == 200


def test_read_full_paper_scrolls_to_embedded_viewer(app_client):
    data = app_client.get("/research").data
    assert b'<a class="rp-btn rp-btn--primary" href="#paper">Read Full Paper</a>' in data
    assert b'id="paper"' in data
    assert b'data-pdf-src="/research/paper.pdf#view=FitH&amp;navpanes=0"' in data


def test_research_page_has_no_publication_status_labels(app_client):
    # The page presents the paper without any status label, and must not
    # imply formal publication either.
    data = app_client.get("/research").data.lower()
    for phrase in (
        b"manuscript", b"preprint", b"peer review", b"peer-review",
        b"doi.org", b"arxiv:", b"accepted at", b"published in",
    ):
        assert phrase not in data, phrase


def test_research_page_overrides_default_social_meta(app_client):
    data = app_client.get("/research").data
    assert b'<meta property="og:type" content="article">' in data
    assert b'content="' + PAPER_TITLE + b'"' in data
    assert b"Free Selective Mutism Games for Kids" not in data
    assert data.count(b'property="og:title"') == 1


def test_default_social_meta_unchanged_on_homepage(app_client):
    data = app_client.get("/").data
    assert b"MyBraveSprout | Free Selective Mutism Games for Kids" in data
    assert data.count(b'property="og:title"') == 1


def test_paper_pdf_is_public_and_inline(app_client):
    resp = app_client.get("/research/paper.pdf")
    assert resp.status_code == 200
    assert resp.mimetype == "application/pdf"
    assert resp.data.startswith(b"%PDF")
    assert "attachment" not in resp.headers.get("Content-Disposition", "")
    resp.close()


def test_paper_pdf_download_has_descriptive_filename(app_client):
    resp = app_client.get("/research/paper.pdf?download=1")
    assert resp.status_code == 200
    disposition = resp.headers.get("Content-Disposition", "")
    assert disposition.startswith("attachment")
    assert "Sekhri_Parameter-Efficient_Trustworthy_Transformers_Stress_Detection_Reddit.pdf" in disposition
    resp.close()


def test_research_assets_exist(app_client):
    for path in (
        "/static/css/research.css",
        "/static/js/research.js",
        "/static/research/research-og.jpg",
    ):
        resp = app_client.get(path)
        assert resp.status_code == 200, path
        resp.close()


def test_sitemap_lists_research(app_client):
    assert b"/research</loc>" in app_client.get("/sitemap.xml").data


def test_public_nav_links_to_research(app_client):
    for path in ("/", "/our-story"):
        data = app_client.get(path).data
        assert b'href="/research" class="top-tab">Research</a>' in data, path
