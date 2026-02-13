"""Atom 1.0 feed output — https://www.rfc-editor.org/rfc/rfc4287"""
import hashlib
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from typing import List
from xml.dom.minidom import parseString

from clawler.models import Article

ATOM_NS = "http://www.w3.org/2005/Atom"


class AtomFormatter:
    """Format articles as an Atom 1.0 feed document."""

    def format(
        self,
        articles: List[Article],
        title: str = "Clawler News Digest",
        feed_url: str = "",
        site_url: str = "",
    ) -> str:
        feed = ET.Element("feed", xmlns=ATOM_NS)

        ET.SubElement(feed, "title").text = title
        ET.SubElement(feed, "id").text = feed_url or "urn:clawler:feed"
        ET.SubElement(feed, "generator", uri="https://github.com/clawdiard/clawler").text = "Clawler"

        now = datetime.now(timezone.utc).isoformat()
        ET.SubElement(feed, "updated").text = now

        if feed_url:
            ET.SubElement(feed, "link", href=feed_url, rel="self", type="application/atom+xml")
        if site_url:
            ET.SubElement(feed, "link", href=site_url, rel="alternate", type="text/html")

        for a in articles:
            entry = ET.SubElement(feed, "entry")
            ET.SubElement(entry, "title").text = a.title
            ET.SubElement(entry, "link", href=a.url, rel="alternate")

            # Stable ID from URL hash
            uid = hashlib.sha256(a.url.encode()).hexdigest()[:16]
            ET.SubElement(entry, "id").text = f"urn:clawler:article:{uid}"

            if a.timestamp:
                ET.SubElement(entry, "published").text = a.timestamp.isoformat()
                ET.SubElement(entry, "updated").text = a.timestamp.isoformat()
            else:
                ET.SubElement(entry, "updated").text = now

            if a.summary:
                ET.SubElement(entry, "summary", type="text").text = a.summary

            # Source as author
            author = ET.SubElement(entry, "author")
            ET.SubElement(author, "name").text = a.source

            # Category
            if a.category and a.category != "general":
                ET.SubElement(entry, "category", term=a.category)

            # Tags as additional categories
            for tag in (a.tags or []):
                ET.SubElement(entry, "category", term=tag)

        raw = ET.tostring(feed, encoding="unicode", xml_declaration=True)
        return parseString(raw).toprettyxml(indent="  ")
