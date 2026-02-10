from __future__ import annotations

import base64
import json
import logging
import re
from datetime import datetime, timedelta, timezone

from fastmcp import Context

from slack_fast_mcp.cache import Cache
from slack_fast_mcp.sanitize import wrap_slack_content
from slack_fast_mcp.server import mcp
from slack_fast_mcp.slack_client import SlackClient
from slack_fast_mcp.text import attachments_to_text, blocks_to_text, process_text, timestamp_to_rfc3339
from slack_fast_mcp.types import Message

logger = logging.getLogger(__name__)

VALID_FILTER_KEYS = frozenset(
    {"is", "in", "from", "with", "before", "after", "on", "during"}
)

MONTH_MAP: dict[str, int] = {
    "january": 1,
    "jan": 1,
    "february": 2,
    "feb": 2,
    "march": 3,
    "mar": 3,
    "april": 4,
    "apr": 4,
    "may": 5,
    "june": 6,
    "jun": 6,
    "july": 7,
    "jul": 7,
    "august": 8,
    "aug": 8,
    "september": 9,
    "sep": 9,
    "sept": 9,
    "october": 10,
    "oct": 10,
    "november": 11,
    "nov": 11,
    "december": 12,
    "dec": 12,
}


async def conversations_search_messages(
    client: SlackClient,
    cache: Cache,
    *,
    search_query: str = "",
    filter_in_channel: str = "",
    filter_in_im_or_mpim: str = "",
    filter_users_with: str = "",
    filter_users_from: str = "",
    filter_date_before: str = "",
    filter_date_after: str = "",
    filter_date_on: str = "",
    filter_date_during: str = "",
    filter_threads_only: bool = False,
    cursor: str = "",
    limit: int = 20,
) -> str:
    raw_query = search_query.strip()
    free_text, filters = split_query(raw_query)

    if filter_threads_only:
        _add_filter(filters, "is", "thread")

    if filter_in_channel:
        f = _param_format_channel(filter_in_channel, cache)
        _add_filter(filters, "in", f)
    elif filter_in_im_or_mpim:
        f = _param_format_user(filter_in_im_or_mpim, cache)
        _add_filter(filters, "in", f)

    if filter_users_with:
        f = _param_format_user(filter_users_with, cache)
        _add_filter(filters, "with", f)

    if filter_users_from:
        f = _param_format_user(filter_users_from, cache)
        _add_filter(filters, "from", f)

    date_map = build_date_filters(
        filter_date_before, filter_date_after, filter_date_on, filter_date_during
    )
    for key, val in date_map.items():
        _add_filter(filters, key, val)

    final_query = build_query(free_text, filters)

    # Parse cursor
    page = 1
    if cursor:
        try:
            decoded = base64.b64decode(cursor).decode()
        except Exception:
            raise ValueError(f"invalid cursor: {cursor}")
        parts = decoded.split(":")
        if len(parts) != 2:
            raise ValueError(f"invalid cursor: {cursor}")
        try:
            page = int(parts[1])
            if page < 1:
                raise ValueError()
        except ValueError:
            raise ValueError(f"invalid cursor page: {cursor}")

    # Clamp limit
    if limit < 1:
        limit = 1
    if limit > 100:
        limit = 100

    resp = await client.search_messages(query=final_query, count=limit, page=page)
    matches = resp.get("messages", {}).get("matches", [])
    pagination = resp.get("messages", {}).get("pagination", {})

    messages = _convert_search_messages(matches, cache)

    current_page = pagination.get("page", 1)
    page_count = pagination.get("page_count", 1)
    if messages and current_page < page_count:
        next_cursor_raw = f"page:{current_page + 1}"
        messages[-1].cursor = base64.b64encode(next_cursor_raw.encode()).decode()

    return json.dumps(
        [m.model_dump(by_alias=True) for m in messages],
        ensure_ascii=False,
    )


def split_query(q: str) -> tuple[list[str], dict[str, list[str]]]:
    free_text: list[str] = []
    filters: dict[str, list[str]] = {}
    for tok in q.split():
        parts = tok.split(":", 1)
        if len(parts) == 2 and parts[0].lower() in VALID_FILTER_KEYS:
            key = parts[0].lower()
            filters.setdefault(key, []).append(parts[1])
        else:
            free_text.append(tok)
    return free_text, filters


def _add_filter(filters: dict[str, list[str]], key: str, val: str) -> None:
    existing = filters.get(key, [])
    if val not in existing:
        filters.setdefault(key, []).append(val)


def build_query(free_text: list[str], filters: dict[str, list[str]]) -> str:
    parts: list[str] = list(free_text)
    for key in ("is", "in", "from", "with", "before", "after", "on", "during"):
        for val in filters.get(key, []):
            parts.append(f"{key}:{val}")
    return " ".join(parts)


def parse_flexible_date(date_str: str) -> str:
    date_str = date_str.strip()

    # Standard formats
    standard_formats = [
        "%Y-%m-%d",
        "%Y/%m/%d",
        "%m-%d-%Y",
        "%m/%d/%Y",
        "%b %d, %Y",
        "%B %d, %Y",
        "%d %b %Y",
        "%d %B %Y",
    ]
    for fmt in standard_formats:
        try:
            t = datetime.strptime(date_str, fmt)
            return t.strftime("%Y-%m-%d")
        except ValueError:
            continue

    # Month-Year patterns: "January 2024" or "2024 January"
    month_year_re = re.compile(r"^(\d{4})\s+([A-Za-z]+)$|^([A-Za-z]+)\s+(\d{4})$")
    m = month_year_re.match(date_str)
    if m:
        if m.group(1) and m.group(2):
            year = int(m.group(1))
            mon_str = m.group(2).lower()
        else:
            year = int(m.group(4))
            mon_str = m.group(3).lower()
        if mon_str in MONTH_MAP:
            return datetime(year, MONTH_MAP[mon_str], 1).strftime("%Y-%m-%d")

    # Day-Month-Year: "2 Jan 2024"
    dmy_re = re.compile(r"^(\d{1,2})[-\s]+([A-Za-z]+)[-\s]+(\d{4})$")
    m = dmy_re.match(date_str)
    if m:
        day = int(m.group(1))
        mon_str = m.group(2).lower()
        year = int(m.group(3))
        if mon_str in MONTH_MAP:
            try:
                t = datetime(year, MONTH_MAP[mon_str], day)
                if t.day == day:
                    return t.strftime("%Y-%m-%d")
            except ValueError:
                pass

    # Month-Day-Year: "Jan 2 2024"
    mdy_re = re.compile(r"^([A-Za-z]+)[-\s]+(\d{1,2})[-\s]+(\d{4})$")
    m = mdy_re.match(date_str)
    if m:
        mon_str = m.group(1).lower()
        day = int(m.group(2))
        year = int(m.group(3))
        if mon_str in MONTH_MAP:
            try:
                t = datetime(year, MONTH_MAP[mon_str], day)
                if t.day == day:
                    return t.strftime("%Y-%m-%d")
            except ValueError:
                pass

    # Year-Month-Day: "2024 Jan 2"
    ymd_re = re.compile(r"^(\d{4})[-\s]+([A-Za-z]+)[-\s]+(\d{1,2})$")
    m = ymd_re.match(date_str)
    if m:
        year = int(m.group(1))
        mon_str = m.group(2).lower()
        day = int(m.group(3))
        if mon_str in MONTH_MAP:
            try:
                t = datetime(year, MONTH_MAP[mon_str], day)
                if t.day == day:
                    return t.strftime("%Y-%m-%d")
            except ValueError:
                pass

    # Relative dates
    lower = date_str.lower()
    now = datetime.now(tz=timezone.utc)

    if lower == "today":
        return now.strftime("%Y-%m-%d")
    if lower == "yesterday":
        return (now - timedelta(days=1)).strftime("%Y-%m-%d")
    if lower == "tomorrow":
        return (now + timedelta(days=1)).strftime("%Y-%m-%d")

    days_ago_re = re.compile(r"^(\d+)\s+days?\s+ago$")
    m = days_ago_re.match(lower)
    if m:
        days = int(m.group(1))
        return (now - timedelta(days=days)).strftime("%Y-%m-%d")

    raise ValueError(f"unable to parse date: {date_str}")


def build_date_filters(before: str, after: str, on: str, during: str) -> dict[str, str]:
    out: dict[str, str] = {}

    if on:
        if during or before or after:
            raise ValueError("'on' cannot be combined with other date filters")
        out["on"] = parse_flexible_date(on)
        return out

    if during:
        if before or after:
            raise ValueError("'during' cannot be combined with 'before' or 'after'")
        out["during"] = parse_flexible_date(during)
        return out

    if after:
        out["after"] = parse_flexible_date(after)
    if before:
        out["before"] = parse_flexible_date(before)

    if after and before:
        a = datetime.strptime(out["after"], "%Y-%m-%d")
        b = datetime.strptime(out["before"], "%Y-%m-%d")
        if a > b:
            raise ValueError("'after' date is after 'before' date")

    return out


def _param_format_user(raw: str, cache: Cache) -> str:
    raw = raw.strip()
    users = cache.users

    # Slack user ID (U or W prefix)
    if raw.startswith("U") or raw.startswith("W"):
        u = users.users.get(raw)
        if not u:
            raise ValueError(f"user {raw!r} not found")
        return f"<@{u['id']}>"

    # Strip leading <@ or @
    if raw.startswith("<@"):
        raw = raw[2:]
    if raw.startswith("@"):
        raw = raw[1:]

    uid = users.users_inv.get(raw)
    if not uid:
        raise ValueError(f"user {raw!r} not found")
    return f"<@{uid}>"


def _param_format_channel(raw: str, cache: Cache) -> str:
    raw = raw.strip()
    channels = cache.channels

    if raw.startswith("#"):
        cid = channels.channels_inv.get(raw)
        if not cid:
            raise ValueError(f"channel {raw!r} not found")
        ch = channels.channels.get(cid)
        return ch.name.lstrip("#") if ch else raw.lstrip("#")

    if raw.startswith("C") or raw.startswith("G"):
        ch = channels.channels.get(raw)
        if not ch:
            raise ValueError(f"channel {raw!r} not found")
        return ch.name.lstrip("#")

    raise ValueError(f"invalid channel format: {raw!r}")


def _convert_search_messages(matches: list[dict], cache: Cache) -> list[Message]:
    messages: list[Message] = []

    for msg in matches:
        user_id = msg.get("user", "") or msg.get("username", "")
        user_name, real_name = _get_user_info(user_id, cache)

        if user_name == user_id and not msg.get("user") and msg.get("username"):
            user_name = msg["username"]
            real_name = msg["username"]

        # Extract thread_ts from permalink
        thread_ts = ""
        permalink = msg.get("permalink", "")
        if "thread_ts=" in permalink:
            try:
                from urllib.parse import parse_qs, urlparse

                parsed = urlparse(permalink)
                thread_ts = parse_qs(parsed.query).get("thread_ts", [""])[0]
            except Exception:
                pass

        try:
            ts = timestamp_to_rfc3339(msg.get("ts", ""))
        except (ValueError, IndexError):
            continue

        msg_text = msg.get("text", "")
        att_text = attachments_to_text(msg_text, msg.get("attachments", []))
        blk_text = blocks_to_text(msg.get("blocks", []))
        full_text = msg_text + att_text + blk_text

        channel_name = msg.get("channel", {}).get("name", "")

        messages.append(
            Message(
                msgID=msg.get("ts", ""),
                userID=msg.get("user", ""),
                userName=wrap_slack_content(user_name),
                realName=wrap_slack_content(real_name),
                channelID=f"#{channel_name}" if channel_name else "",
                threadTs=thread_ts,
                text=wrap_slack_content(process_text(full_text)),
                time=ts,
                reactions="",
                hasMedia=False,
            )
        )

    return messages


def _get_user_info(user_id: str, cache: Cache) -> tuple[str, str]:
    user_data = cache.users.users.get(user_id)
    if user_data:
        return user_data.get("name", user_id), user_data.get("real_name", user_id)
    return user_id, user_id


# --- MCP tool wrapper ---


@mcp.tool(
    name="conversations_search_messages",
    description=(
        "Search messages in a public channel, private channel, or direct message (DM, or IM) "
        "conversation using filters. All filters are optional; if not provided then search_query is required."
    ),
)
async def tool_conversations_search_messages(
    search_query: str = "",
    filter_in_channel: str = "",
    filter_in_im_or_mpim: str = "",
    filter_users_with: str = "",
    filter_users_from: str = "",
    filter_date_before: str = "",
    filter_date_after: str = "",
    filter_date_on: str = "",
    filter_date_during: str = "",
    filter_threads_only: bool = False,
    cursor: str = "",
    limit: int = 20,
    ctx: Context = None,
) -> str:
    """Search messages.

    Args:
        search_query: Search query or full Slack message URL.
        filter_in_channel: Channel ID/name to filter (C/G prefix or #name).
        filter_in_im_or_mpim: IM/MPIM ID or @username.
        filter_users_with: User ID/name for thread/DM conversations.
        filter_users_from: User ID/name who sent the message.
        filter_date_before: Date filter in YYYY-MM-DD or flexible format.
        filter_date_after: Date filter in YYYY-MM-DD or flexible format.
        filter_date_on: Exact date (cannot combine with before/after).
        filter_date_during: Month/period (cannot combine with on/before/after).
        filter_threads_only: Only return thread messages.
        cursor: Pagination cursor.
        limit: Max results (1-100). Default 20.
    """
    app_ctx = ctx.request_context.lifespan_context
    if app_ctx["config"].is_bot_token:
        raise ValueError(
            "conversations_search_messages is not available for bot tokens (xoxb). "
            "Use a user token (xoxp) instead."
        )
    return await conversations_search_messages(
        app_ctx["client"],
        app_ctx["cache"],
        search_query=search_query,
        filter_in_channel=filter_in_channel,
        filter_in_im_or_mpim=filter_in_im_or_mpim,
        filter_users_with=filter_users_with,
        filter_users_from=filter_users_from,
        filter_date_before=filter_date_before,
        filter_date_after=filter_date_after,
        filter_date_on=filter_date_on,
        filter_date_during=filter_date_during,
        filter_threads_only=filter_threads_only,
        cursor=cursor,
        limit=limit,
    )
