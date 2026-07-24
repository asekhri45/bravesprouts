"""Regression tests for search-facing brand metadata and favicon isolation."""

import json
import os
import struct
from html.parser import HTMLParser
from urllib.parse import urlparse

import app as app_module


CANONICAL_HOME_URL = "https://www.mybravesprout.com/"
ORGANIZATION_LOGO_URL = (
    "https://www.mybravesprout.com/"
    "static/images/favicon1/android-chrome-512x512.png"
)


class HeadMetadataParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.icon_links = []
        self.canonical_links = []
        self.meta_tags = []
        self.jsonld_documents = []
        self._jsonld_parts = None

    def handle_starttag(self, tag, attrs):
        attributes = dict(attrs)

        if tag == "link":
            rel = attributes.get("rel", "").lower()
            if rel in {"icon", "shortcut icon", "apple-touch-icon"}:
                self.icon_links.append(attributes)
            if rel == "canonical":
                self.canonical_links.append(attributes)

        if tag == "meta":
            self.meta_tags.append(attributes)

        if (
            tag == "script"
            and attributes.get("type", "").lower() == "application/ld+json"
        ):
            self._jsonld_parts = []

    def handle_data(self, data):
        if self._jsonld_parts is not None:
            self._jsonld_parts.append(data)

    def handle_endtag(self, tag):
        if tag == "script" and self._jsonld_parts is not None:
            self.jsonld_documents.append(json.loads("".join(self._jsonld_parts)))
            self._jsonld_parts = None


def _parse_head_metadata(html):
    parser = HeadMetadataParser()
    parser.feed(html.decode())
    return parser


def _jsonld_entities(documents):
    entities = []

    for document in documents:
        if isinstance(document, list):
            entities.extend(document)
        elif isinstance(document, dict) and isinstance(document.get("@graph"), list):
            entities.extend(document["@graph"])
        else:
            entities.append(document)

    return entities


def _entity_types(entity):
    entity_type = entity.get("@type", [])
    return {entity_type} if isinstance(entity_type, str) else set(entity_type)


def test_homepage_has_one_authoritative_organization_and_website(app_client):
    response = app_client.get("/")

    assert response.status_code == 200
    parsed = _parse_head_metadata(response.data)
    entities = _jsonld_entities(parsed.jsonld_documents)
    organizations = [
        entity for entity in entities if "Organization" in _entity_types(entity)
    ]
    websites = [entity for entity in entities if "WebSite" in _entity_types(entity)]

    assert len(organizations) == 1
    assert len(websites) == 1

    organization = organizations[0]
    assert organization["name"] == "MyBraveSprout"
    assert organization["url"] == CANONICAL_HOME_URL
    assert organization["logo"] == {
        "@type": "ImageObject",
        "url": ORGANIZATION_LOGO_URL,
        "width": 512,
        "height": 512,
    }

    website = websites[0]
    assert website["name"] == "MyBraveSprout"
    assert website["url"] == CANONICAL_HOME_URL


def test_homepage_uses_the_canonical_origin_and_is_indexable(app_client):
    response = app_client.get("/")
    parsed = _parse_head_metadata(response.data)
    robots_values = [
        meta.get("content", "").lower()
        for meta in parsed.meta_tags
        if meta.get("name", "").lower() == "robots"
    ]

    assert parsed.canonical_links == [
        {"rel": "canonical", "href": CANONICAL_HOME_URL}
    ]
    assert all("noindex" not in value for value in robots_values)
    assert "noindex" not in response.headers.get("X-Robots-Tag", "").lower()


def test_organization_logo_is_absolute_https_and_public(app_client):
    response = app_client.get("/")
    parsed = _parse_head_metadata(response.data)
    entities = _jsonld_entities(parsed.jsonld_documents)
    organization = next(
        entity for entity in entities if "Organization" in _entity_types(entity)
    )
    logo_url = organization["logo"]["url"]
    logo_parts = urlparse(logo_url)

    assert logo_parts.scheme == "https"
    assert logo_parts.netloc == "www.mybravesprout.com"
    assert "localhost" not in logo_url
    assert "127.0.0.1" not in logo_url
    assert logo_parts.path.startswith("/static/images/favicon1/")

    logo_response = app_client.get(logo_parts.path)
    assert logo_response.status_code == 200
    assert logo_response.mimetype == "image/png"
    assert "Location" not in logo_response.headers


def test_organization_logo_file_is_native_square_and_large_enough():
    logo_path = os.path.join(
        os.path.dirname(app_module.__file__),
        "static",
        "images",
        "favicon1",
        "android-chrome-512x512.png",
    )

    assert os.path.isfile(logo_path)

    with open(logo_path, "rb") as logo_file:
        header = logo_file.read(24)

    assert header[:8] == b"\x89PNG\r\n\x1a\n"
    width, height = struct.unpack(">II", header[16:24])
    assert width == height
    assert width >= 112
    assert (width, height) == (512, 512)


def test_browser_tab_favicon_configuration_is_unchanged(app_client):
    response = app_client.get("/")
    parsed = _parse_head_metadata(response.data)

    assert parsed.icon_links == [
        {
            "rel": "icon",
            "type": "image/png",
            "sizes": "96x96",
            "href": (
                "https://www.mybravesprout.com/"
                "static/images/favicon-96x96.png"
            ),
        },
        {
            "rel": "shortcut icon",
            "type": "image/x-icon",
            "href": "https://www.mybravesprout.com/static/images/favicon.ico",
        },
        {
            "rel": "apple-touch-icon",
            "sizes": "180x180",
            "href": (
                "https://www.mybravesprout.com/"
                "static/images/logo-512x512.png"
            ),
        },
    ]
    assert all("favicon1" not in link["href"] for link in parsed.icon_links)


def test_game_layout_keeps_its_original_favicon_reference():
    with app_module.app.test_request_context("/"):
        rendered = app_module.render_template("activity_layout.html")

    parsed = _parse_head_metadata(rendered.encode())
    assert parsed.icon_links == [
        {
            "rel": "icon",
            "type": "image/x-icon",
            "href": "/static/images/favicon.ico",
        }
    ]


def test_organization_is_not_duplicated_on_non_home_pages(app_client):
    response = app_client.get("/login")

    assert response.status_code == 200
    parsed = _parse_head_metadata(response.data)
    entities = _jsonld_entities(parsed.jsonld_documents)
    organizations = [
        entity for entity in entities if "Organization" in _entity_types(entity)
    ]

    assert organizations == []


def test_article_publisher_uses_the_same_organization_logo(app_client):
    slug = next(iter(app_module.PARENT_ACADEMY_ARTICLES))
    response = app_client.get(f"/parent-resources/article/{slug}")

    assert response.status_code == 200
    parsed = _parse_head_metadata(response.data)
    entities = _jsonld_entities(parsed.jsonld_documents)
    article = next(entity for entity in entities if "Article" in _entity_types(entity))

    assert article["publisher"] == {
        "@type": "Organization",
        "name": "MyBraveSprout",
        "url": CANONICAL_HOME_URL,
        "logo": {
            "@type": "ImageObject",
            "url": ORGANIZATION_LOGO_URL,
            "width": 512,
            "height": 512,
        },
    }
