from __future__ import annotations

import re
from datetime import datetime, timezone
from urllib.parse import urlparse


def timestamp_to_rfc3339(slack_ts: str) -> str:
    parts = slack_ts.split(".")
    if len(parts) != 2:
        raise ValueError(f"invalid slack timestamp format: {slack_ts}")

    seconds = int(parts[0])
    microseconds = int(parts[1])
    dt = datetime.fromtimestamp(seconds, tz=timezone.utc).replace(
        microsecond=microseconds
    )
    return dt.strftime("%Y-%m-%dT%H:%M:%SZ")


def workspace_from_url(url: str) -> str:
    parsed = urlparse(url)
    host = parsed.hostname or ""
    parts = host.split(".")
    if len(parts) < 3:
        raise ValueError(f"invalid Slack URL: {url!r}")
    return parts[0]


def process_text(text: str) -> str:
    return _filter_special_chars(text)


def attachment_to_text(att: dict) -> str:
    parts: list[str] = []

    if att.get("title"):
        parts.append(f"Title: {att['title']}")
    if att.get("author_name"):
        parts.append(f"Author: {att['author_name']}")
    if att.get("pretext"):
        parts.append(f"Pretext: {att['pretext']}")
    if att.get("text"):
        parts.append(f"Text: {att['text']}")
    if att.get("footer"):
        ts_val = str(att.get("ts", ""))
        if ts_val and "." not in ts_val:
            ts_val = ts_val + ".000000"
        try:
            ts_str = timestamp_to_rfc3339(ts_val)
        except (ValueError, IndexError):
            ts_str = ""
        parts.append(f"Footer: {att['footer']} @ {ts_str}")

    result = "; ".join(parts)
    result = result.replace("\n", " ")
    result = result.replace("\r", " ")
    result = result.replace("\t", " ")
    result = result.replace("(", "[")
    result = result.replace(")", "]")
    return result.strip()


def attachments_to_text(msg_text: str, attachments: list[dict]) -> str:
    if not attachments:
        return ""

    descriptions: list[str] = []
    for att in attachments:
        plain = attachment_to_text(att)
        if plain:
            descriptions.append(plain)

    if not descriptions:
        return ""

    prefix = ". " if msg_text else ""
    return prefix + ", ".join(descriptions)


def _rich_text_element_to_text(element: dict) -> str:
    """Extract text from a single rich_text child element."""
    etype = element.get("type", "")
    if etype == "text":
        return element.get("text", "")
    if etype == "link":
        return element.get("text", "") or element.get("url", "")
    if etype == "emoji":
        return f":{element.get('name', '')}:"
    if etype == "user":
        return f"<@{element.get('user_id', '')}>"
    if etype == "channel":
        return f"<#{element.get('channel_id', '')}>"
    if etype == "broadcast":
        return f"@{element.get('range', 'everyone')}"
    return ""


def _rich_text_block_to_text(elements: list[dict]) -> str:
    """Extract text from rich_text block top-level elements."""
    parts: list[str] = []
    for el in elements:
        etype = el.get("type", "")
        children = el.get("elements", [])
        if etype in ("rich_text_section", "rich_text_preformatted", "rich_text_quote"):
            text = "".join(_rich_text_element_to_text(c) for c in children)
            if text:
                parts.append(text)
        elif etype == "rich_text_list":
            for item in children:
                item_children = item.get("elements", [])
                text = "".join(_rich_text_element_to_text(c) for c in item_children)
                if text:
                    parts.append(f"- {text}")
    return "\n".join(parts)


def _block_to_text(block: dict) -> str:
    """Extract text content from a single Block Kit block."""
    btype = block.get("type", "")

    if btype in ("section", "header"):
        parts: list[str] = []
        text_obj = block.get("text")
        if text_obj and text_obj.get("text"):
            parts.append(text_obj["text"])
        for field in block.get("fields", []):
            if field.get("text"):
                parts.append(field["text"])
        return " | ".join(parts)

    if btype == "rich_text":
        return _rich_text_block_to_text(block.get("elements", []))

    if btype == "context":
        texts = []
        for el in block.get("elements", []):
            if el.get("type") in ("plain_text", "mrkdwn") and el.get("text"):
                texts.append(el["text"])
        return " ".join(texts)

    if btype == "table":
        row_texts: list[str] = []
        for row in block.get("rows", []):
            cell_texts: list[str] = []
            for cell in row:
                ctype = cell.get("type", "")
                if ctype == "raw_text":
                    cell_texts.append(cell.get("text", ""))
                elif ctype == "rich_text":
                    cell_texts.append(
                        _rich_text_block_to_text(cell.get("elements", []))
                    )
            row_texts.append(" | ".join(cell_texts))
        return "\n".join(row_texts)

    return ""


def blocks_to_text(blocks: list[dict]) -> str:
    """Extract text from Block Kit blocks and return as a single string."""
    if not blocks:
        return ""

    parts: list[str] = []
    for block in blocks:
        text = _block_to_text(block)
        if text:
            parts.append(text)

    if not parts:
        return ""

    return ". " + " | ".join(parts)


def _filter_special_chars(text: str) -> str:
    # Handle Slack-style links: <URL|Description>
    slack_link_re = re.compile(r"<(https?://[^>|]+)\|([^>]+)>")
    for m in reversed(list(slack_link_re.finditer(text))):
        url, link_text = m.group(1), m.group(2)
        is_last = text[m.end() :].strip() == ""
        replacement = f"{url} - {link_text}" + ("" if is_last else ",")
        text = text[: m.start()] + replacement + text[m.end() :]

    # Handle markdown links: [Description](URL)
    md_link_re = re.compile(r"\[([^\]]+)\]\((https?://[^)]+)\)")
    for m in reversed(list(md_link_re.finditer(text))):
        link_text, url = m.group(1), m.group(2)
        is_last = text[m.end() :].strip() == ""
        replacement = f"{url} - {link_text}" + ("" if is_last else ",")
        text = text[: m.start()] + replacement + text[m.end() :]

    # Handle HTML links
    html_link_re = re.compile(r"""<a\s+href=["']([^"']+)["'][^>]*>([^<]+)</a>""")
    for m in reversed(list(html_link_re.finditer(text))):
        url, link_text = m.group(1), m.group(2)
        is_last = text[m.end() :].strip() == ""
        replacement = f"{url} - {link_text}" + ("" if is_last else ",")
        text = text[: m.start()] + replacement + text[m.end() :]

    # Protect URLs from special char filtering
    url_re = re.compile(r"https?://[^\s<>\"{}|\\^`\[\]]+")
    urls = url_re.findall(text)
    for i, url in enumerate(urls):
        placeholder = f"___URL_PLACEHOLDER_{i}___"
        text = text.replace(url, placeholder, 1)

    # Remove special characters (keep alphanumeric, unicode letters, spaces, basic punctuation)
    clean_re = re.compile(r"[^0-9\w\s.,\-_:/\?=&%]", re.UNICODE)
    text = clean_re.sub("", text)

    # Restore URLs
    for i, url in enumerate(urls):
        placeholder = f"___URL_PLACEHOLDER_{i}___"
        text = text.replace(placeholder, url, 1)

    # Collapse whitespace
    text = re.sub(r"[ \t]+", " ", text)
    return text.strip()
