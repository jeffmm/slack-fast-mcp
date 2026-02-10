from __future__ import annotations

import logging

from fastmcp import Context

from slack_fast_mcp.cache import Cache
from slack_fast_mcp.config import Config, is_channel_allowed
from slack_fast_mcp.server import mcp
from slack_fast_mcp.slack_client import SlackClient

logger = logging.getLogger(__name__)


async def reactions_add(
    client: SlackClient,
    cache: Cache,
    config: Config,
    *,
    channel_id: str,
    timestamp: str,
    emoji: str,
) -> str:
    _validate_reaction_params(cache, config, channel_id, timestamp, emoji)
    channel_id = _resolve_channel(cache, channel_id)
    emoji = emoji.strip(":")

    if not is_channel_allowed(channel_id, config.reaction_tool):
        raise ValueError(
            f"reactions tools are not allowed for channel {channel_id!r}, applied policy: {config.reaction_tool}"
        )

    await client.reactions_add(channel=channel_id, timestamp=timestamp, name=emoji)
    return f"Successfully added :{emoji}: reaction to message {timestamp} in channel {channel_id}"


async def reactions_remove(
    client: SlackClient,
    cache: Cache,
    config: Config,
    *,
    channel_id: str,
    timestamp: str,
    emoji: str,
) -> str:
    _validate_reaction_params(cache, config, channel_id, timestamp, emoji)
    channel_id = _resolve_channel(cache, channel_id)
    emoji = emoji.strip(":")

    if not is_channel_allowed(channel_id, config.reaction_tool):
        raise ValueError(
            f"reactions tools are not allowed for channel {channel_id!r}, applied policy: {config.reaction_tool}"
        )

    await client.reactions_remove(channel=channel_id, timestamp=timestamp, name=emoji)
    return f"Successfully removed :{emoji}: reaction from message {timestamp} in channel {channel_id}"


def _validate_reaction_params(
    cache: Cache, config: Config, channel_id: str, timestamp: str, emoji: str
) -> None:
    if not config.reaction_tool:
        raise ValueError(
            "by default, the reactions tools are disabled to guard Slack workspaces against accidental spamming. "
            "To enable them, set the SLACK_MCP_REACTION_TOOL environment variable to true, 1, or comma separated list of channels "
            "to limit where the MCP can manage reactions, e.g. 'SLACK_MCP_REACTION_TOOL=C1234567890,D0987654321', 'SLACK_MCP_REACTION_TOOL=!C1234567890' "
            "to enable all except one or 'SLACK_MCP_REACTION_TOOL=true' for all channels and DMs"
        )

    if not channel_id:
        raise ValueError("channel_id is required")
    if not timestamp:
        raise ValueError("timestamp is required")
    if not emoji.strip(":"):
        raise ValueError("emoji is required")


def _resolve_channel(cache: Cache, channel: str) -> str:
    if channel.startswith("#") or channel.startswith("@"):
        resolved = cache.resolve_channel_id(channel)
        if resolved is None:
            raise ValueError(f"channel {channel!r} not found")
        return resolved
    return channel


# --- MCP tool wrappers ---


@mcp.tool(
    name="reactions_add",
    description="Add an emoji reaction to a message.",
)
async def tool_reactions_add(
    channel_id: str,
    timestamp: str,
    emoji: str,
    ctx: Context = None,
) -> str:
    """Add a reaction.

    Args:
        channel_id: Channel ID (Cxxxxxxxxxx) or name (#channel or @username_dm).
        timestamp: Message timestamp in format 1234567890.123456.
        emoji: Emoji name without colons (e.g. thumbsup, heart, rocket).
    """
    app_ctx = ctx.request_context.lifespan_context
    return await reactions_add(
        app_ctx["client"],
        app_ctx["cache"],
        app_ctx["config"],
        channel_id=channel_id,
        timestamp=timestamp,
        emoji=emoji,
    )


@mcp.tool(
    name="reactions_remove",
    description="Remove an emoji reaction from a message.",
)
async def tool_reactions_remove(
    channel_id: str,
    timestamp: str,
    emoji: str,
    ctx: Context = None,
) -> str:
    """Remove a reaction.

    Args:
        channel_id: Channel ID (Cxxxxxxxxxx) or name (#channel or @username_dm).
        timestamp: Message timestamp in format 1234567890.123456.
        emoji: Emoji name without colons (e.g. thumbsup, heart, rocket).
    """
    app_ctx = ctx.request_context.lifespan_context
    return await reactions_remove(
        app_ctx["client"],
        app_ctx["cache"],
        app_ctx["config"],
        channel_id=channel_id,
        timestamp=timestamp,
        emoji=emoji,
    )
