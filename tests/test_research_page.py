"""Tests for the public research page (/research) and its manuscript PDF."""
from conftest import login_as_user

PAPER_TITLE = b"Toward Parameter-Efficient and Trustworthy Transformers for Stress Detection in Reddit Posts"


def test_research_page_is_public(app_client):
    resp = app_client.get("/research")
    assert resp.status_code == 200
    assert PAPER_TITLE in resp.data
    assert b"Aarav Sekhri" in resp.data
    assert b"Dr. Bartosz Krawczyk" in resp.data
    assert b"Cite This Work" in resp.data
    assert b'href="/research/paper.pdf"' in resp.data
    assert b'href="/research/paper.pdf?download=1"' in resp.data


def test_research_page_works_when_logged_in(app_client, make_user):
    user_id = make_user(email="researchviewer@example.test")
    login_as_user(app_client, user_id, parent_setup_complete=True)
    assert app_client.get("/research").status_code == 200


def test_research_page_never_claims_publication_status(app_client):
    data = app_client.get("/research").data
    assert b"Not peer reviewed" in data
    for phrase in (b"doi.org", b"arXiv:", b"Peer-reviewed", b"Accepted at", b"Published in"):
        assert phrase not in data


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
        "/static/research/fig2-modeling-frameworks.webp",
        "/static/research/fig5-stress-terms-by-outcome.webp",
        "/static/research/research-og.jpg",
    ):
        resp = app_client.get(path)
        assert resp.status_code == 200, path
        resp.close()


def test_sitemap_lists_research(app_client):
    assert b"/research</loc>" in app_client.get("/sitemap.xml").data
