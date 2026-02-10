from __future__ import annotations

import json
import logging

from fastmcp import Context

from slack_fast_mcp.cache import Cache
from slack_fast_mcp.config import Config, is_channel_allowed
from slack_fast_mcp.sanitize import wrap_slack_content
from slack_fast_mcp.server import mcp
from slack_fast_mcp.slack_client import SlackClient
from slack_fast_mcp.text import process_text, timestamp_to_rfc3339
from slack_fast_mcp.types import Message

logger = logging.getLogger(__name__)


async def conversations_add_message(
    client: SlackClient,
    cache: Cache,
    config: Config,
    *,
    channel_id: str,
    payload: str,
    thread_ts: str = "",
    content_type: str = "text/markdown",
) -> str:
    if not config.add_message_tool:
        raise ValueError(
            "by default, the conversations_add_message tool is disabled to guard Slack workspaces against accidental spamming. "
            "To enable it, set the SLACK_MCP_ADD_MESSAGE_TOOL environment variable to true, 1, or comma separated list of channels "
            "to limit where the MCP can post messages, e.g. 'SLACK_MCP_ADD_MESSAGE_TOOL=C1234567890,D0987654321', 'SLACK_MCP_ADD_MESSAGE_TOOL=!C1234567890' "
            "to enable all except one or 'SLACK_MCP_ADD_MESSAGE_TOOL=true' for all channels and DMs"
        )

    # Resolve channel name
    channel_id = _resolve_channel(cache, channel_id)

    if not is_channel_allowed(channel_id, config.add_message_tool):
        raise ValueError(
            f"conversations_add_message tool is not allowed for channel {channel_id!r}, applied policy: {config.add_message_tool}"
        )

    if not payload:
        raise ValueError("text must be a string")

    if thread_ts and "." not in thread_ts:
        raise ValueError(
            "thread_ts must be a valid timestamp in format 1234567890.123456"
        )

    if content_type not in ("text/plain", "text/markdown"):
        raise ValueError("content_type must be either 'text/plain' or 'text/markdown'")

    mrkdwn = content_type == "text/markdown"

    resp = await client.chat_post_message(
        channel=channel_id,
        text=payload,
        thread_ts=thread_ts,
        mrkdwn=mrkdwn,
        unfurl_links=False,
        unfurl_media=False,
    )

    resp_channel = resp.get("channel", channel_id)
    resp_ts = resp.get("ts", "")

    # Mark conversation if configured
    if config.add_message_mark and resp_ts:
        try:
            await client.conversations_mark(channel=resp_channel, ts=resp_ts)
        except Exception:
            logger.warning("Failed to mark conversation")

    # Fetch the posted message
    history = await client.conversations_history(
        channel=resp_channel,
        limit=1,
        oldest=resp_ts,
        latest=resp_ts,
        inclusive=True,
    )
    raw_messages = history.get("messages", [])
    messages = _convert_messages(raw_messages, resp_channel, cache)

    return json.dumps(
        [m.model_dump(by_alias=True) for m in messages],
        ensure_ascii=False,
    )


def _resolve_channel(cache: Cache, channel: str) -> str:
    if channel.startswith("#") or channel.startswith("@"):
        resolved = cache.resolve_channel_id(channel)
        if resolved is None:
            raise ValueError(f"channel {channel!r} not found")
        return resolved
    return channel


def _convert_messages(
    raw_messages: list[dict], channel_id: str, cache: Cache
) -> list[Message]:
    messages: list[Message] = []
    for msg in raw_messages:
        user_id = msg.get("user", "")
        user_data = cache.users.users.get(user_id)
        user_name = user_data.get("name", user_id) if user_data else user_id
        real_name = user_data.get("real_name", user_id) if user_data else user_id

        try:
            ts = timestamp_to_rfc3339(msg.get("ts", ""))
        except (ValueError, IndexError):
            continue

        messages.append(
            Message(
                msgID=msg.get("ts", ""),
                userID=user_id,
                userName=wrap_slack_content(user_name),
                realName=wrap_slack_content(real_name),
                channelID=channel_id,
                threadTs=msg.get("thread_ts", ""),
                text=wrap_slack_content(process_text(msg.get("text", ""))),
                time=ts,
            )
        )
    return messages


# --- MCP tool wrapper ---


@mcp.tool(
    name="conversations_add_message",
    description="Add a message to a public channel, private channel, or direct message (DM, or IM) conversation.",
)
async def tool_conversations_add_message(
    channel_id: str,
    payload: str = "",
    thread_ts: str = "",
    content_type: str = "text/markdown",
    ctx: Context = None,
) -> str:
    """Send a message.

    Args:
        channel_id: Channel ID (Cxxxxxxxxxx) or name (#channel or @username_dm).
        payload: Message text in specified content_type format.
        thread_ts: Thread timestamp to reply to (optional).
        content_type: 'text/markdown' or 'text/plain'. Default 'text/markdown'.
    """
    app_ctx = ctx.request_context.lifespan_context
    return await conversations_add_message(
        app_ctx["client"],
        app_ctx["cache"],
        app_ctx["config"],
        channel_id=channel_id,
        payload=payload,
        thread_ts=thread_ts,
        content_type=content_type,
    )
