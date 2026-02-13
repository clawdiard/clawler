"""Tests for Atom feed formatter."""
import xml.etree.ElementTree as ET
from datetime import datetime, timezone

from clawler.formatters.atom import AtomFormatter
from clawler.models import Article

ATOM_NS = "http://www.w3.org/2005/Atom"


def _ns(tag):
    return f"{{{ATOM_NS}}}{tag}"


def _make_articles():
    return [
        Article(
            title="Test Article One",
            url="https://example.com/one",
            source="Example News",
            summary="First test article summary.",
            timestamp=datetime(2026, 2, 13, 12, 0, 0, tzinfo=timezone.utc),
            category="tech",
            tags=["python", "ai"],
        ),
        Article(
            title="Test Article Two",
            url="https://example.com/two",
            source="Other News",
            summary="",
            timestamp=None,
            category="general",
        ),
    ]


def test_atom_produces_valid_xml():
    fmt = AtomFormatter()
    output = fmt.format(_make_articles())
    root = ET.fromstring(output)
    assert root.tag == _ns("feed")


def test_atom_feed_metadata():
    fmt = AtomFormatter()
    output = fmt.format(_make_articles(), title="My Feed", feed_url="https://example.com/feed.xml")
    root = ET.fromstring(output)
    assert root.find(_ns("title")).text == "My Feed"
    assert root.find(_ns("generator")).text == "Clawler"
    assert root.find(_ns("id")).text == "https://example.com/feed.xml"
    # self link
    links = root.findall(_ns("link"))
    assert any(l.get("rel") == "self" for l in links)


def test_atom_entry_count():
    fmt = AtomFormatter()
    output = fmt.format(_make_articles())
    root = ET.fromstring(output)
    entries = root.findall(_ns("entry"))
    assert len(entries) == 2


def test_atom_entry_fields():
    fmt = AtomFormatter()
    output = fmt.format(_make_articles())
    root = ET.fromstring(output)
    entry = root.findall(_ns("entry"))[0]
    assert entry.find(_ns("title")).text == "Test Article One"
    assert entry.find(_ns("link")).get("href") == "https://example.com/one"
    assert entry.find(_ns("summary")).text == "First test article summary."
    assert entry.find(_ns("published")).text is not None
    author = entry.find(_ns("author"))
    assert author.find(_ns("name")).text == "Example News"


def test_atom_entry_categories_and_tags():
    fmt = AtomFormatter()
    output = fmt.format(_make_articles())
    root = ET.fromstring(output)
    entry = root.findall(_ns("entry"))[0]
    cats = [c.get("term") for c in entry.findall(_ns("category"))]
    assert "tech" in cats
    assert "python" in cats
    assert "ai" in cats


def test_atom_no_summary_omitted():
    fmt = AtomFormatter()
    output = fmt.format(_make_articles())
    root = ET.fromstring(output)
    entry = root.findall(_ns("entry"))[1]
    assert entry.find(_ns("summary")) is None


def test_atom_empty_list():
    fmt = AtomFormatter()
    output = fmt.format([])
    root = ET.fromstring(output)
    assert len(root.findall(_ns("entry"))) == 0


def test_atom_general_category_omitted():
    """Articles with category='general' should not emit a category element for it."""
    fmt = AtomFormatter()
    output = fmt.format(_make_articles())
    root = ET.fromstring(output)
    entry = root.findall(_ns("entry"))[1]  # "general" category article
    cats = entry.findall(_ns("category"))
    assert len(cats) == 0
