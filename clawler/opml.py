"""OPML import/export for RSS feed lists."""
import xml.etree.ElementTree as ET
from typing import List
from xml.dom.minidom import parseString


def export_opml(feeds: List[dict], title: str = "Clawler Feeds") -> str:
    """Export a feed list to OPML 2.0 XML string."""
    opml = ET.Element("opml", version="2.0")
    head = ET.SubElement(opml, "head")
    ET.SubElement(head, "title").text = title
    body = ET.SubElement(opml, "body")

    # Group by category
    by_cat: dict[str, list] = {}
    for f in feeds:
        cat = f.get("category", "general")
        by_cat.setdefault(cat, []).append(f)

    for cat, cat_feeds in sorted(by_cat.items()):
        outline = ET.SubElement(body, "outline", text=cat, title=cat)
        for f in cat_feeds:
            ET.SubElement(outline, "outline",
                          type="rss",
                          text=f.get("source", ""),
                          title=f.get("source", ""),
                          xmlUrl=f["url"],
                          category=cat)

    raw = ET.tostring(opml, encoding="unicode", xml_declaration=True)
    return parseString(raw).toprettyxml(indent="  ")


def import_opml(xml_content: str) -> List[dict]:
    """Import feeds from OPML XML string. Returns list of feed dicts."""
    root = ET.fromstring(xml_content)
    feeds = []

    def _walk(element, parent_cat="general"):
        for outline in element.findall("outline"):
            xml_url = outline.get("xmlUrl")
            if xml_url:
                feeds.append({
                    "url": xml_url,
                    "source": outline.get("text") or outline.get("title") or xml_url,
                    "category": outline.get("category") or parent_cat,
                })
            else:
                # Category folder
                cat = outline.get("text") or outline.get("title") or parent_cat
                _walk(outline, cat)

    body = root.find("body")
    if body is not None:
        _walk(body)

    return feeds
