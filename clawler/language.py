"""Lightweight language detection for articles.

Uses character-frequency heuristics and common word lists to detect article language
from title and summary text. No external dependencies required.

Supported detections: English, Spanish, French, German, Portuguese, Italian, Dutch,
Chinese, Japanese, Korean, Russian, Arabic.

Usage:
    clawler --lang en           # English articles only
    clawler --lang en,es        # English or Spanish
    clawler --exclude-lang zh   # Exclude Chinese articles
"""
from __future__ import annotations

import re
import unicodedata
from typing import List, Optional

from clawler.models import Article

# Common stop words per language (high-frequency function words)
_LANG_WORDS = {
    "en": frozenset({
        "the", "and", "for", "that", "with", "this", "from", "have", "has",
        "are", "was", "were", "been", "will", "would", "could", "should",
        "about", "into", "more", "your", "their", "which", "when", "what",
        "than", "after", "before", "also", "just", "how", "its", "over",
    }),
    "es": frozenset({
        "que", "los", "las", "del", "por", "con", "una", "para", "como",
        "pero", "sus", "más", "este", "esta", "ser", "entre", "cuando",
        "muy", "sin", "sobre", "también", "hasta", "desde", "donde",
    }),
    "fr": frozenset({
        "les", "des", "une", "que", "est", "dans", "pour", "qui", "sur",
        "pas", "plus", "par", "avec", "son", "sont", "mais", "ont", "ses",
        "aux", "cette", "tout", "nous", "vous", "leur", "entre", "après",
    }),
    "de": frozenset({
        "der", "die", "und", "den", "von", "das", "ist", "des", "auf",
        "für", "mit", "sich", "dem", "nicht", "ein", "eine", "als",
        "auch", "nach", "wie", "aus", "bei", "oder", "nur", "noch",
    }),
    "pt": frozenset({
        "que", "para", "com", "uma", "dos", "por", "não", "mais", "como",
        "mas", "foi", "são", "sua", "seu", "das", "nos", "entre", "pelo",
        "tem", "ser", "está", "sobre", "também", "quando", "muito",
    }),
    "it": frozenset({
        "che", "per", "una", "del", "con", "non", "sono", "della", "anche",
        "più", "suo", "sua", "dei", "dal", "gli", "nel", "alla", "questo",
        "essere", "come", "stato", "tra", "dopo", "tutto", "molto",
    }),
    "nl": frozenset({
        "het", "een", "van", "dat", "met", "voor", "zijn", "maar", "niet",
        "ook", "nog", "uit", "naar", "wel", "dan", "hun", "alle", "deze",
    }),
}

# CJK and script-based detection ranges
_CJK_RE = re.compile(r"[\u4e00-\u9fff\u3400-\u4dbf]")
_HIRAGANA_KATAKANA_RE = re.compile(r"[\u3040-\u309f\u30a0-\u30ff]")
_HANGUL_RE = re.compile(r"[\uac00-\ud7af\u1100-\u11ff]")
_CYRILLIC_RE = re.compile(r"[\u0400-\u04ff]")
_ARABIC_RE = re.compile(r"[\u0600-\u06ff]")

_WORD_RE = re.compile(r"[a-zà-öø-ÿ]+")


def detect_language(article: Article) -> str:
    """Detect the probable language of an article.

    Returns an ISO 639-1 language code: 'en', 'es', 'fr', 'de', 'pt', 'it',
    'nl', 'zh', 'ja', 'ko', 'ru', 'ar', or 'unknown'.
    """
    text = f"{article.title} {article.summary}"

    # Script-based detection (high confidence)
    if _HIRAGANA_KATAKANA_RE.search(text):
        return "ja"
    if _HANGUL_RE.search(text):
        return "ko"
    cjk_count = len(_CJK_RE.findall(text))
    if cjk_count > len(text) * 0.1:
        return "zh"
    cyrillic_count = len(_CYRILLIC_RE.findall(text))
    if cyrillic_count > len(text) * 0.15:
        return "ru"
    arabic_count = len(_ARABIC_RE.findall(text))
    if arabic_count > len(text) * 0.15:
        return "ar"

    # Word-frequency-based detection for Latin-script languages
    words = _WORD_RE.findall(text.lower())
    if not words:
        return "unknown"

    scores = {}
    for lang, stopwords in _LANG_WORDS.items():
        matches = sum(1 for w in words if w in stopwords)
        scores[lang] = matches / len(words) if words else 0

    best_lang = max(scores, key=scores.get)
    best_score = scores[best_lang]

    # Require minimum confidence
    if best_score < 0.05:
        return "unknown"

    return best_lang


def filter_by_language(
    articles: List[Article],
    lang: Optional[str] = None,
    exclude_lang: Optional[str] = None,
) -> List[Article]:
    """Filter articles by detected language.

    Args:
        articles: List of articles to filter.
        lang: Comma-separated language codes to keep (e.g. 'en,es').
        exclude_lang: Comma-separated language codes to exclude.

    Returns:
        Filtered list of articles.
    """
    if not lang and not exclude_lang:
        return articles

    include = set(l.strip().lower() for l in lang.split(",")) if lang else None
    exclude = set(l.strip().lower() for l in exclude_lang.split(",")) if exclude_lang else set()

    result = []
    for a in articles:
        detected = detect_language(a)
        if exclude and detected in exclude:
            continue
        if include and detected not in include and detected != "unknown":
            continue
        result.append(a)
    return result
