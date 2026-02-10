from __future__ import annotations

import json
import logging
import re

from fastmcp import Context

from slack_fast_mcp.cache import Cache
from slack_fast_mcp.sanitize import wrap_slack_content
from slack_fast_mcp.server import mcp
from slack_fast_mcp.types import UserSearchResult

logger = logging.getLogger(__name__)


async def users_search(
    cache: Cache,
    *,
    query: str,
    limit: int = 10,
) -> str:
    query = query.strip()
    if not query:
        raise ValueError("query is required")

    if limit <= 0:
        limit = 10
    if limit > 100:
        limit = 100

    pattern = re.compile(re.escape(query), re.IGNORECASE)
    results: list[UserSearchResult] = []

    for user in cache.users.users.values():
        if user.get("deleted", False):
            continue

        name = user.get("name", "")
        real_name = user.get("real_name", "")
        profile = user.get("profile", {})
        display_name = profile.get("display_name", "")
        email = profile.get("email", "")

        if (
            pattern.search(name)
            or pattern.search(real_name)
            or pattern.search(display_name)
            or pattern.search(email)
        ):
            # Find DM channel
            dm_channel_id = ""
            for ch in cache.channels.channels.values():
                if ch.is_im and ch.user == user["id"]:
                    dm_channel_id = ch.id
                    break

            results.append(
                UserSearchResult(
                    userID=user["id"],
                    userName=wrap_slack_content(name),
                    realName=wrap_slack_content(real_name),
                    displayName=wrap_slack_content(display_name),
                    email=email,
                    title=profile.get("title", ""),
                    dmChannelID=dm_channel_id,
                )
            )

            if len(results) >= limit:
                break

    if not results:
        return "No users found matching the query."

    return json.dumps(
        [r.model_dump(by_alias=True) for r in results],
        ensure_ascii=False,
    )


# --- MCP tool wrapper ---


@mcp.tool(
    name="users_search",
    description="Search for users by name, email, or display name. Returns user details and DM channel ID if available.",
)
async def tool_users_search(
    query: str,
    limit: int = 10,
    ctx: Context = None,
) -> str:
    """Search users.

    Args:
        query: Search term - matches against real name, display name, username, or email.
        limit: Max results (1-100). Default 10.
    """
    app_ctx = ctx.request_context.lifespan_context
    return await users_search(
        app_ctx["cache"],
        query=query,
        limit=limit,
    )
