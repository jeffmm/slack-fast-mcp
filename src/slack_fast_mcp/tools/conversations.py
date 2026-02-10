from __future__ import annotations

import json
import logging
from datetime import datetime, timedelta, timezone

from slack_fast_mcp.cache import Cache
from slack_fast_mcp.sanitize import wrap_slack_content
from fastmcp import Context

from slack_fast_mcp.server import mcp
from slack_fast_mcp.slack_client import SlackClient
from slack_fast_mcp.text import attachments_to_text, blocks_to_text, process_text, timestamp_to_rfc3339
from slack_fast_mcp.types import Message

logger = logging.getLogger(__name__)

DEFAULT_NUMERIC_LIMIT = 50
DEFAULT_EXPRESSION_LIMIT = "1d"


async def conversations_history(
    client: SlackClient,
    cache: Cache,
    *,
    channel_id: str,
    limit: str = "1d",
    cursor: str = "",
    include_activity_messages: bool = False,
) -> str:
    channel_id = _resolve_channel(cache, channel_id)

    parsed_limit, oldest, latest = _parse_limit(limit, cursor)

    kwargs: dict = {
        "channel": channel_id,
        "limit": parsed_limit,
        "inclusive": False,
    }
    if oldest:
        kwargs["oldest"] = oldest
    if latest:
        kwargs["latest"] = latest
    if cursor:
        kwargs["cursor"] = cursor

    resp = await client.conversations_history(**kwargs)
    messages = _convert_history_messages(
        resp.get("messages", []),
        channel_id,
        cache,
        include_activity_messages,
    )

    has_more = resp.get("has_more", False)
    next_cursor = resp.get("response_metadata", {}).get("next_cursor", "")
    if messages and has_more and next_cursor:
        messages[-1].cursor = next_cursor

    return _serialize_messages(messages)


async def conversations_replies(
    client: SlackClient,
    cache: Cache,
    *,
    channel_id: str,
    thread_ts: str,
    limit: str = "1d",
    cursor: str = "",
    include_activity_messages: bool = False,
) -> str:
    channel_id = _resolve_channel(cache, channel_id)

    parsed_limit, oldest, latest = _parse_limit(limit, cursor)

    kwargs: dict = {
        "channel": channel_id,
        "ts": thread_ts,
        "limit": parsed_limit,
        "inclusive": False,
    }
    if oldest:
        kwargs["oldest"] = oldest
    if latest:
        kwargs["latest"] = latest
    if cursor:
        kwargs["cursor"] = cursor

    resp = await client.conversations_replies(**kwargs)
    raw_messages = resp.get("messages", [])
    has_more = resp.get("has_more", False)
    next_cursor = resp.get("response_metadata", {}).get("next_cursor", "")

    messages = _convert_history_messages(
        raw_messages,
        channel_id,
        cache,
        include_activity_messages,
    )

    if messages and has_more and next_cursor:
        messages[-1].cursor = next_cursor

    return _serialize_messages(messages)


def _resolve_channel(cache: Cache, channel: str) -> str:
    if channel.startswith("#") or channel.startswith("@"):
        resolved = cache.resolve_channel_id(channel)
        if resolved is None:
            raise ValueError(f"channel {channel!r} not found")
        return resolved
    return channel


def _parse_limit(limit: str, cursor: str) -> tuple[int, str, str]:
    if not limit:
        limit = DEFAULT_EXPRESSION_LIMIT

    suffix = limit[-1] if limit else ""
    if suffix in ("d", "w", "m"):
        return _limit_by_expression(limit)
    elif cursor == "":
        return _limit_by_numeric(limit), "", ""
    else:
        return 0, "", ""


def _limit_by_numeric(limit: str) -> int:
    if not limit:
        return DEFAULT_NUMERIC_LIMIT
    try:
        return int(limit)
    except ValueError:
        raise ValueError(f"invalid numeric limit: {limit!r}")


def _limit_by_expression(limit: str) -> tuple[int, str, str]:
    if not limit:
        limit = DEFAULT_EXPRESSION_LIMIT
    if len(limit) < 2:
        raise ValueError(f"invalid duration limit {limit!r}: too short")

    suffix = limit[-1]
    try:
        n = int(limit[:-1])
    except ValueError:
        raise ValueError(
            f"invalid duration limit {limit!r}: must be a positive integer followed by 'd', 'w', or 'm'"
        )
    if n <= 0:
        raise ValueError(
            f"invalid duration limit {limit!r}: must be a positive integer followed by 'd', 'w', or 'm'"
        )

    now = datetime.now(tz=timezone.utc)
    start_of_today = now.replace(hour=0, minute=0, second=0, microsecond=0)

    if suffix == "d":
        oldest_time = start_of_today - timedelta(days=n - 1)
    elif suffix == "w":
        oldest_time = start_of_today - timedelta(days=n * 7 - 1)
    elif suffix == "m":
        # Subtract months: go back n months from start of today
        month = start_of_today.month - n
        year = start_of_today.year
        while month <= 0:
            month += 12
            year -= 1
        oldest_time = start_of_today.replace(year=year, month=month)
    else:
        raise ValueError(
            f"invalid duration limit {limit!r}: must end in 'd', 'w', or 'm'"
        )

    latest_ts = f"{int(now.timestamp())}.000000"
    oldest_ts = f"{int(oldest_time.timestamp())}.000000"
    return 100, oldest_ts, latest_ts


def _convert_history_messages(
    raw_messages: list[dict],
    channel_id: str,
    cache: Cache,
    include_activity: bool,
) -> list[Message]:
    messages: list[Message] = []

    for msg in raw_messages:
        subtype = msg.get("subtype", "")
        if (
            subtype
            and subtype not in ("bot_message", "thread_broadcast")
            and not include_activity
        ):
            continue

        user_id = msg.get("user", "")
        user_name, real_name = _get_user_info(user_id, cache)

        if user_name == user_id and subtype == "bot_message":
            bot_username = msg.get("username", "")
            if bot_username:
                user_name = bot_username
                real_name = bot_username

        try:
            ts = timestamp_to_rfc3339(msg.get("ts", ""))
        except (ValueError, IndexError):
            continue

        msg_text = msg.get("text", "")
        att_text = attachments_to_text(msg_text, msg.get("attachments", []))
        blk_text = blocks_to_text(msg.get("blocks", []))
        full_text = msg_text + att_text + blk_text

        reactions_parts = []
        for r in msg.get("reactions", []):
            reactions_parts.append(f"{r.get('name', '')}:{r.get('count', 0)}")
        reactions_str = "|".join(reactions_parts)

        bot_name = ""
        bot_profile = msg.get("bot_profile")
        if bot_profile and bot_profile.get("name"):
            bot_name = bot_profile["name"]

        files = msg.get("files", [])
        file_count = len(files)
        attachment_ids = ",".join(f.get("id", "") for f in files)
        has_media = file_count > 0

        messages.append(
            Message(
                msgID=msg.get("ts", ""),
                userID=user_id,
                userName=wrap_slack_content(user_name),
                realName=wrap_slack_content(real_name),
                channelID=channel_id,
                threadTs=msg.get("thread_ts", ""),
                text=wrap_slack_content(process_text(full_text)),
                time=ts,
                reactions=reactions_str,
                botName=wrap_slack_content(bot_name) if bot_name else "",
                fileCount=file_count,
                attachmentIDs=attachment_ids,
                hasMedia=has_media,
            )
        )

    return messages


def _get_user_info(user_id: str, cache: Cache) -> tuple[str, str]:
    user_data = cache.users.users.get(user_id)
    if user_data:
        return user_data.get("name", user_id), user_data.get("real_name", user_id)
    return user_id, user_id


def _serialize_messages(messages: list[Message]) -> str:
    return json.dumps(
        [m.model_dump(by_alias=True) for m in messages],
        ensure_ascii=False,
    )


# --- MCP tool wrappers ---


@mcp.tool(
    name="conversations_history",
    description=(
        "Get messages from the channel (or DM) by channel_id. "
        "The cursor field in the last message of the response is used for pagination if not empty."
    ),
)
async def tool_conversations_history(
    channel_id: str,
    limit: str = "1d",
    cursor: str = "",
    include_activity_messages: bool = False,
    ctx: Context = None,
) -> str:
    """Get messages from a channel or DM.

    Args:
        channel_id: ID of the channel (Cxxxxxxxxxx) or name (#channel or @username_dm).
        limit: Time range (1d, 1w, 30d, 90d) or message count (50). Must be empty when cursor is provided.
        cursor: Pagination cursor from previous response.
        include_activity_messages: If true, include activity messages like channel_join/channel_leave.
    """
    app_ctx = ctx.request_context.lifespan_context
    return await conversations_history(
        app_ctx["client"],
        app_ctx["cache"],
        channel_id=channel_id,
        limit=limit,
        cursor=cursor,
        include_activity_messages=include_activity_messages,
    )


@mcp.tool(
    name="conversations_replies",
    description=(
        "Get a thread of messages posted to a conversation by channel_id and thread_ts. "
        "The cursor field in the last message of the response is used for pagination if not empty."
    ),
)
async def tool_conversations_replies(
    channel_id: str,
    thread_ts: str,
    limit: str = "1d",
    cursor: str = "",
    include_activity_messages: bool = False,
    ctx: Context = None,
) -> str:
    """Get thread replies.

    Args:
        channel_id: ID of the channel (Cxxxxxxxxxx) or name (#channel or @username_dm).
        thread_ts: Thread timestamp in format 1234567890.123456.
        limit: Time range (1d, 1w, 30d) or message count (50). Must be empty when cursor is provided.
        cursor: Pagination cursor from previous response.
        include_activity_messages: If true, include activity messages.
    """
    app_ctx = ctx.request_context.lifespan_context
    return await conversations_replies(
        app_ctx["client"],
        app_ctx["cache"],
        channel_id=channel_id,
        thread_ts=thread_ts,
        limit=limit,
        cursor=cursor,
        include_activity_messages=include_activity_messages,
    )
