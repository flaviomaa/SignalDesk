from dataclasses import asdict, dataclass
from datetime import datetime
from typing import Optional


SOURCE_ALIAS_MAP = {
    "bsi-cert": "BSI-CERT",
    "bsi cert": "BSI-CERT",
    "bsi": "BSI-CERT",
    "bmj": "BMJ",
    "edpb": "EDPB",
    "edps": "EDPS",
    "enisa": "ENISA",
    "baylda": "BayLDA",
    "eurlex": "EUR-Lex",
    "eur-lex": "EUR-Lex",
    "ai act": "AI Act",
    "aiact": "AI Act",
    "artificialintelligenceact": "AI Act",
    "the eu ai act newsletter": "AI Act",
}

SOURCE_CATEGORY_MAP = {
    "BSI-CERT": "cybersecurity",
    "BMJ": "law",
    "EDPB": "privacy",
    "EDPS": "privacy",
    "ENISA": "cybersecurity",
    "BayLDA": "privacy",
    "EUR-Lex": "law",
    "AI Act": "ai-regulation",
}

SOURCE_LANGUAGE_MAP = {
    "BSI-CERT": "de",
    "BMJ": "de",
    "EDPB": "en",
    "EDPS": "en",
    "ENISA": "en",
    "BayLDA": "de",
    "EUR-Lex": "en",
    "AI Act": "en",
}


def clean_text(value: Optional[str]) -> str:
    if value is None:
        return ""
    return " ".join(str(value).split()).strip()


def infer_source_from_fields(
    source_raw: Optional[str] = None,
    title: Optional[str] = None,
    link: Optional[str] = None,
    url: Optional[str] = None,
    content: Optional[str] = None,
) -> str:
    candidates = [
        clean_text(source_raw),
        clean_text(title),
        clean_text(link),
        clean_text(url),
        clean_text(content)[:500],
    ]

    for raw in candidates:
        if not raw:
            continue

        key = raw.lower()

        if key in SOURCE_ALIAS_MAP:
            return SOURCE_ALIAS_MAP[key]

        if "artificialintelligenceact" in key:
            return "AI Act"
        if "the eu ai act newsletter" in key:
            return "AI Act"
        if "eu ai act newsletter" in key:
            return "AI Act"
        if "future of life institute" in key and "ai act" in key:
            return "AI Act"
        if "substack.com" in key and "ai-act" in key:
            return "AI Act"
        if "substack.com" in key and "artificialintelligenceact" in key:
            return "AI Act"
        if "ai act" in key:
            return "AI Act"
        if "aiact" in key:
            return "AI Act"

    return normalize_source(source_raw)


def normalize_source(value: Optional[str]) -> str:
    raw = clean_text(value)
    if not raw:
        return "Unknown"

    key = raw.lower()

    if key in SOURCE_ALIAS_MAP:
        return SOURCE_ALIAS_MAP[key]

    if "artificialintelligenceact" in key:
        return "AI Act"
    if "the eu ai act newsletter" in key:
        return "AI Act"
    if "eu ai act newsletter" in key:
        return "AI Act"
    if "ai act" in key:
        return "AI Act"
    if "aiact" in key:
        return "AI Act"

    return raw


def normalize_language(
    source: str,
    language_raw: Optional[str] = None,
    title: Optional[str] = None,
    content: Optional[str] = None,
    link: Optional[str] = None,
    url: Optional[str] = None,
) -> str:
    lang = clean_text(language_raw).lower()

    if lang in {"de", "en"}:
        return lang

    joined = " ".join(
        [
            clean_text(title),
            clean_text(link),
            clean_text(url),
            clean_text(content)[:1000],
        ]
    ).lower()

    if source in SOURCE_LANGUAGE_MAP:
        return SOURCE_LANGUAGE_MAP[source]

    if "artificialintelligenceact" in joined:
        return "en"
    if "the eu ai act newsletter" in joined:
        return "en"
    if "substack.com" in joined and "ai-act" in joined:
        return "en"

    return "de"


@dataclass
class SignalDeskItem:
    source: str
    title: str
    link: str
    date: Optional[str] = None
    content: str = ""
    category: Optional[str] = None
    language: str = "de"
    scraped_at: Optional[str] = None
    is_new: bool = True
    url: Optional[str] = None
    section: Optional[str] = None

    def __post_init__(self) -> None:
        self.source = normalize_source(self.source)
        self.title = clean_text(self.title)
        self.url = clean_text(self.url) or None
        self.link = clean_text(self.link or self.url)
        self.date = clean_text(self.date) or None
        self.content = clean_text(self.content)
        self.section = clean_text(self.section) or None

        if not self.scraped_at:
            self.scraped_at = datetime.now().isoformat()

        self.language = normalize_language(
            source=self.source,
            language_raw=self.language,
            title=self.title,
            content=self.content,
            link=self.link,
            url=self.url,
        )

        self.category = clean_text(self.category) or SOURCE_CATEGORY_MAP.get(self.source, "general")

    def to_dict(self) -> dict:
        data = asdict(self)
        data["link"] = self.link or self.url or ""
        return data


def normalize_entry(raw: dict) -> dict:
    title = raw.get("title", "")
    link = raw.get("link") or raw.get("url", "")
    url = raw.get("url")
    content = raw.get("content") or raw.get("body") or raw.get("description") or ""

    source = infer_source_from_fields(
        source_raw=raw.get("source"),
        title=title,
        link=link,
        url=url,
        content=content,
    )

    item = SignalDeskItem(
        source=source,
        title=title,
        link=link,
        date=raw.get("date") or raw.get("published"),
        content=content,
        category=raw.get("category"),
        language=raw.get("language"),
        scraped_at=raw.get("scraped_at"),
        is_new=raw.get("is_new", True),
        url=url,
        section=raw.get("section"),
    )
    return item.to_dict()


def normalize_batch(items: list[dict]) -> list[dict]:
    return [normalize_entry(item) for item in items]