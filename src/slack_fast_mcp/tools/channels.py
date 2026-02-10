from __future__ import annotations

import base64
import json
import logging

from fastmcp import Context

from slack_fast_mcp.cache import Cache, CachedChannel
from slack_fast_mcp.sanitize import wrap_slack_content
from slack_fast_mcp.server import mcp
from slack_fast_mcp.types import ChannelInfo

logger = logging.getLogger(__name__)

VALID_CHANNEL_TYPES = frozenset({"public_channel", "private_channel", "im", "mpim"})


async def channels_list(
    cache: Cache,
    *,
    channel_types: str,
    sort: str = "popularity",
    limit: int = 100,
    cursor: str = "",
) -> str:
    # Parse and validate types
    requested_types: list[str] = []
    for t in channel_types.split(","):
        t = t.strip()
        if t in VALID_CHANNEL_TYPES:
            requested_types.append(t)

    if not requested_types:
        requested_types = ["public_channel", "private_channel"]

    # Clamp limit
    if limit <= 0:
        limit = 100
    if limit > 999:
        limit = 999

    all_channels = cache.channels.channels

    # Filter by type
    filtered = _filter_channels_by_types(all_channels, requested_types)

    # Paginate
    paged, next_cursor = _paginate_channels(filtered, cursor, limit)

    # Sort
    if sort == "popularity":
        paged.sort(key=lambda c: c.member_count, reverse=True)

    # Build result
    result: list[ChannelInfo] = []
    for ch in paged:
        result.append(
            ChannelInfo(
                id=ch.id,
                name=ch.name,
                topic=wrap_slack_content(ch.topic),
                purpose=wrap_slack_content(ch.purpose),
                memberCount=ch.member_count,
            )
        )

    if result and next_cursor:
        result[-1].cursor = next_cursor

    return json.dumps(
        [c.model_dump(by_alias=True) for c in result],
        ensure_ascii=False,
    )


def _filter_channels_by_types(
    channels: dict[str, CachedChannel], types: list[str]
) -> list[CachedChannel]:
    type_set = set(types)
    result: list[CachedChannel] = []

    for ch in channels.values():
        if (
            "public_channel" in type_set
            and not ch.is_private
            and not ch.is_im
            and not ch.is_mpim
        ):
            result.append(ch)
        elif (
            "private_channel" in type_set
            and ch.is_private
            and not ch.is_im
            and not ch.is_mpim
        ):
            result.append(ch)
        elif "im" in type_set and ch.is_im:
            result.append(ch)
        elif "mpim" in type_set and ch.is_mpim:
            result.append(ch)

    return result


def _paginate_channels(
    channels: list[CachedChannel], cursor: str, limit: int
) -> tuple[list[CachedChannel], str]:
    # Sort by ID for stable pagination
    channels.sort(key=lambda c: c.id)

    start_index = 0
    if cursor:
        try:
            decoded = base64.b64decode(cursor).decode()
            for i, ch in enumerate(channels):
                if ch.id > decoded:
                    start_index = i
                    break
        except Exception:
            pass

    end_index = min(start_index + limit, len(channels))
    paged = channels[start_index:end_index]

    next_cursor = ""
    if end_index < len(channels) and paged:
        next_cursor = base64.b64encode(paged[-1].id.encode()).decode()

    return paged, next_cursor


# --- MCP tool wrapper ---


@mcp.tool(
    name="channels_list",
    description="Get list of channels.",
)
async def tool_channels_list(
    channel_types: str,
    sort: str = "popularity",
    limit: int = 100,
    cursor: str = "",
    ctx: Context = None,
) -> str:
    """List channels.

    Args:
        channel_types: Comma-separated types: public_channel, private_channel, im, mpim.
        sort: Sort type. Allowed: 'popularity'.
        limit: Max items (1-999). Default 100.
        cursor: Pagination cursor from previous response.
    """
    app_ctx = ctx.request_context.lifespan_context
    return await channels_list(
        app_ctx["cache"],
        channel_types=channel_types,
        sort=sort,
        limit=limit,
        cursor=cursor,
    )
