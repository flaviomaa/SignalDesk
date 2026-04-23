from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional


@dataclass
class SignalDeskItem:
    """Standardisiertes SignalDesk-Artikel-Format."""

    source: str
    title: str
    link: str
    date: Optional[str] = None
    content: Optional[str] = None
    category: Optional[str] = None
    language: str = "de"
    scraped_at: Optional[str] = None
    is_new: bool = True
    url: Optional[str] = None
    section: Optional[str] = None

    def __post_init__(self):
        if self.scraped_at is None:
            self.scraped_at = datetime.now().isoformat()
        if self.language == "en" or self.language == "de":
            pass
        elif self.source.lower() in ["edps", "eurlex", "enisa", "edpb"]:
            self.language = "en"
        else:
            self.language = "de"

    def to_dict(self) -> dict:
        return {
            "source": self.source,
            "title": self.title,
            "link": self.link or self.url,
            "date": self.date,
            "content": self.content,
            "category": self.category,
            "language": self.language,
            "scraped_at": self.scraped_at,
            "is_new": self.is_new,
        }


SOURCE_CATEGORY_MAP = {
    "BMJ": "recht",
    "EURLEX": "recht",
    "EUR-Lex": "recht",
    "EDPB": "datenschutz",
    "EDPS": "datenschutz",
    "BayLDA": "datenschutz",
    "LfD-Berlin": "datenschutz",
    "LfD Berlin": "datenschutz",
    "LfD-Hessen": "datenschutz",
    "Hessen": "datenschutz",
    "BSI-CERT": "cybersicherheit",
    "BSI-Consumer": "cybersicherheit",
    "ENISA-News": "cybersicherheit",
    "ENISA-Publications": "cybersicherheit",
    "ENISA": "cybersicherheit",
    "AI-Act": "ai",
    "AI Act": "ai",
    "Artificial Intelligence Act": "ai",
}

SOURCE_LANGUAGE_MAP = {
    "BMJ": "de",
    "BayLDA": "de",
    "LfD-Berlin": "de",
    "LfD Berlin": "de",
    "LfD-Hessen": "de",
    "Hessen": "de",
    "EURLEX": "de",
    "EUR-Lex": "de",
    "EDPB": "en",
    "EDPS": "en",
    "BSI-CERT": "de",
    "BSI-Consumer": "de",
    "ENISA-News": "en",
    "ENISA-Publications": "en",
    "ENISA": "en",
    "AI-Act": "en",
    "AI Act": "en",
    "Artificial Intelligence Act": "en",
}


def normalize_source(source: Optional[str]) -> str:
    if not source:
        return "unknown"
    s = source.strip()
    for key, value in SOURCE_CATEGORY_MAP.items():
        if key.lower() in s.lower():
            return key
    return s


def normalize_entry(raw: dict) -> SignalDeskItem:
    source_raw = raw.get("source", raw.get("title", ""))
    source_clean = normalize_source(source_raw)

    category = SOURCE_CATEGORY_MAP.get(source_clean, "sonstige")

    language = SOURCE_LANGUAGE_MAP.get(source_clean, "de")
    language_raw = raw.get("language", None)
    if language_raw:
        language = language_raw

    link = raw.get("link") or raw.get("url", "")
    date = raw.get("date") or raw.get("published", raw.get("published_at"))

    content = raw.get("content", raw.get("body", raw.get("description")))

    title = raw.get("title", "")
    if not title:
        title = raw.get("headline", "Unbenannter Eintrag")

    section = raw.get("section", None)

    return SignalDeskItem(
        source=source_clean,
        title=title,
        link=link,
        date=date,
        content=content,
        category=category,
        language=language,
        scraped_at=datetime.now().isoformat(),
        is_new=raw.get("is_new", True),
        url=link,
        section=section,
    )


def normalize_batch(raw_list: list) -> list:
    normalized = []
    for raw in raw_list:
        try:
            normalized.append(normalize_entry(raw))
        except Exception as e:
            print(f"[WARNUNG] Normalisierung fehlgeschlagen: {e}")
            continue
    return normalized


def save_normalized_json(items: list, output_path: str):
    import json
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump([item.to_dict() for item in items], f, indent=2, ensure_ascii=False)
    print(f"[OK] Normalisierte Daten gespeichert: {output_path}")