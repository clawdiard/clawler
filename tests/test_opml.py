"""Tests for OPML import/export."""
from clawler.opml import export_opml, import_opml


SAMPLE_FEEDS = [
    {"url": "https://example.com/tech.xml", "source": "TechBlog", "category": "tech"},
    {"url": "https://example.com/news.xml", "source": "WorldNews", "category": "world"},
    {"url": "https://example.com/sci.xml", "source": "SciDigest", "category": "science"},
]


class TestExportOPML:
    def test_valid_xml(self):
        output = export_opml(SAMPLE_FEEDS)
        assert '<?xml' in output
        assert '<opml version="2.0">' in output

    def test_contains_feeds(self):
        output = export_opml(SAMPLE_FEEDS)
        assert "TechBlog" in output
        assert "https://example.com/tech.xml" in output

    def test_grouped_by_category(self):
        output = export_opml(SAMPLE_FEEDS)
        assert 'text="tech"' in output
        assert 'text="world"' in output

    def test_custom_title(self):
        output = export_opml(SAMPLE_FEEDS, title="My Feeds")
        assert "My Feeds" in output


class TestImportOPML:
    def test_roundtrip(self):
        xml = export_opml(SAMPLE_FEEDS)
        imported = import_opml(xml)
        assert len(imported) == 3
        urls = {f["url"] for f in imported}
        assert "https://example.com/tech.xml" in urls

    def test_preserves_source_name(self):
        xml = export_opml(SAMPLE_FEEDS)
        imported = import_opml(xml)
        names = {f["source"] for f in imported}
        assert "TechBlog" in names

    def test_flat_opml(self):
        flat = '''<?xml version="1.0"?>
        <opml version="2.0">
          <head><title>Test</title></head>
          <body>
            <outline type="rss" text="Flat" xmlUrl="https://flat.com/rss"/>
          </body>
        </opml>'''
        imported = import_opml(flat)
        assert len(imported) == 1
        assert imported[0]["url"] == "https://flat.com/rss"

    def test_empty_opml(self):
        empty = '<?xml version="1.0"?><opml version="2.0"><head/><body/></opml>'
        assert import_opml(empty) == []
