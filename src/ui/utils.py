"""Utility functions for the Streamlit UI."""

ARTICLE_TYPE_JA_MAP = {
    "ANNOUNCEMENT": "お知らせ",
    "EVENT_REPORT": "イベントレポート",
    "INTERVIEW": "インタビュー",
    "CULTURE": "カルチャー",
}


def format_article_type_ja(article_type: str) -> str:
    """Convert article type to Japanese.

    Args:
        article_type: English article type key.

    Returns:
        Japanese article type name.
    """
    return ARTICLE_TYPE_JA_MAP.get(article_type, article_type)


def truncate_text(text: str, max_length: int = 100) -> str:
    """Truncate text to max length with ellipsis.

    Args:
        text: Text to truncate.
        max_length: Maximum length before truncation.

    Returns:
        Truncated text with ellipsis if needed.
    """
    if len(text) <= max_length:
        return text
    return text[:max_length] + "..."


def parse_sections_to_body(sections: list[dict[str, str]]) -> str:
    """Convert sections list to body text.

    Args:
        sections: List of section dictionaries with heading and body.

    Returns:
        Formatted body text with headings.
    """
    lines = []
    for section in sections:
        lines.append(f"### {section['heading']}")
        lines.append("")
        lines.append(section["body"])
        lines.append("")
    return "\n".join(lines)


def create_download_markdown(data: dict) -> str:
    """Create markdown content for download.

    Args:
        data: Dictionary with article data (titles, lead, sections, closing).

    Returns:
        Formatted markdown string.
    """
    lines = []

    # Title section
    lines.append("# タイトル案")
    lines.append("")
    for i, title in enumerate(data.get("titles", []), 1):
        lines.append(f"{i}. {title}")
    lines.append("")

    # Lead
    lines.append("## リード文")
    lines.append("")
    lines.append(data.get("lead", ""))
    lines.append("")

    # Body sections
    lines.append("## 本文")
    lines.append("")
    for section in data.get("sections", []):
        lines.append(f"### {section['heading']}")
        lines.append("")
        lines.append(section["body"])
        lines.append("")

    # Closing
    lines.append("## 締め")
    lines.append("")
    lines.append(data.get("closing", ""))
    lines.append("")

    # Metadata
    lines.append("---")
    lines.append("")
    lines.append(f"記事タイプ: {data.get('article_type_ja', '不明')}")

    return "\n".join(lines)
