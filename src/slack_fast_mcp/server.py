from __future__ import annotations

import asyncio
import logging
import sys
from contextlib import asynccontextmanager

from fastmcp import FastMCP

from slack_fast_mcp.cache import Cache
from slack_fast_mcp.config import load_config
from slack_fast_mcp.slack_client import SlackClient
from slack_fast_mcp.text import workspace_from_url

logger = logging.getLogger("slack_fast_mcp")


@asynccontextmanager
async def lifespan(server: FastMCP):
    config = load_config()

    # Set up logging
    level = getattr(logging, config.log_level.upper(), logging.INFO)
    logging.basicConfig(
        level=level,
        format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
        stream=sys.stderr,
    )

    logger.info("Starting Slack MCP Server...")

    client = SlackClient(config.token, cookie=config.xoxd_cookie)

    # Auth test
    auth_mode = "cookie (xoxc)" if config.xoxd_cookie else ("bot" if config.is_bot_token else "user")
    logger.info("Authenticating with Slack API (mode=%s)...", auth_mode)
    auth = await client.auth_test()
    workspace = workspace_from_url(auth.get("url", ""))
    logger.info(
        "Authenticated: team=%s user=%s workspace=%s",
        auth.get("team", ""),
        auth.get("user", ""),
        workspace,
    )

    # Warm caches
    cache = Cache(
        client,
        ttl_seconds=config.cache_ttl_seconds,
        users_cache_path=config.users_cache_path,
        channels_cache_path=config.channels_cache_path,
    )
    logger.info("Warming caches...")
    needs_refresh = await cache.warm()
    logger.info("Caches ready")

    # If stale disk cache was used, refresh in the background
    bg_task = None
    if needs_refresh:

        async def _bg_refresh() -> None:
            try:
                logger.info("Starting background cache refresh...")
                await cache.refresh_users(force=True)
                await cache.refresh_channels(force=True)
                logger.info("Background cache refresh complete")
            except Exception:
                logger.warning("Background cache refresh failed", exc_info=True)

        bg_task = asyncio.create_task(_bg_refresh())

    # Store context for tools
    ctx = {"client": client, "cache": cache, "config": config, "workspace": workspace}
    yield ctx

    if bg_task and not bg_task.done():
        bg_task.cancel()


mcp = FastMCP("Slack MCP Server", lifespan=lifespan)

# Importing tool modules triggers @mcp.tool() decorator registration
from slack_fast_mcp.tools import (  # noqa: E402, F401
    attachments,
    channels,
    conversations,
    messages,
    reactions,
    search,
    users,
)

# Importing resource modules triggers @mcp.resource() decorator registration
from slack_fast_mcp.resources import (  # noqa: E402, F401
    channels as _channels_res,
    users as _users_res,
)
