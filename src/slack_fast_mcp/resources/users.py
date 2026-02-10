from __future__ import annotations

import json

from fastmcp import Context

from slack_fast_mcp.cache import Cache
from slack_fast_mcp.sanitize import wrap_slack_content
from slack_fast_mcp.server import mcp
from slack_fast_mcp.types import UserInfo


def get_users_resource(cache: Cache) -> str:
    result: list[UserInfo] = []
    for user in cache.users.users.values():
        result.append(
            UserInfo(
                userID=user.get("id", ""),
                userName=wrap_slack_content(user.get("name", "")),
                realName=wrap_slack_content(user.get("real_name", "")),
            )
        )
    return json.dumps(
        [u.model_dump(by_alias=True) for u in result],
        ensure_ascii=False,
    )


# --- MCP resource wrapper ---


@mcp.resource("slack://{workspace}/users")
async def resource_users(workspace: str, ctx: Context = None) -> str:
    """Directory of Slack users."""
    app_ctx = ctx.request_context.lifespan_context
    return get_users_resource(app_ctx["cache"])
