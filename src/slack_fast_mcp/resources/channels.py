from __future__ import annotations

import json

from fastmcp import Context

from slack_fast_mcp.cache import Cache
from slack_fast_mcp.sanitize import wrap_slack_content
from slack_fast_mcp.server import mcp
from slack_fast_mcp.types import ChannelInfo


def get_channels_resource(cache: Cache) -> str:
    result: list[ChannelInfo] = []
    for ch in cache.channels.channels.values():
        result.append(
            ChannelInfo(
                id=ch.id,
                name=ch.name,
                topic=wrap_slack_content(ch.topic),
                purpose=wrap_slack_content(ch.purpose),
                memberCount=ch.member_count,
            )
        )
    return json.dumps(
        [c.model_dump(by_alias=True) for c in result],
        ensure_ascii=False,
    )


# --- MCP resource wrapper ---


@mcp.resource("slack://{workspace}/channels")
async def resource_channels(workspace: str, ctx: Context = None) -> str:
    """Directory of Slack channels."""
    app_ctx = ctx.request_context.lifespan_context
    return get_channels_resource(app_ctx["cache"])
