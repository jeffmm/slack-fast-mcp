from __future__ import annotations

import os
import sys
from dataclasses import dataclass


@dataclass(frozen=True)
class Config:
    token: str
    is_bot_token: bool
    xoxd_cookie: str = ""
    log_level: str = "info"
    add_message_tool: str = ""
    reaction_tool: str = ""
    attachment_tool: str = ""
    cache_ttl_seconds: int = 3600
    users_cache_path: str = ""
    channels_cache_path: str = ""
    add_message_mark: bool = False
    add_message_unfurling: str = ""


def load_config() -> Config:
    xoxp = os.environ.get("SLACK_MCP_XOXP_TOKEN", "")
    xoxb = os.environ.get("SLACK_MCP_XOXB_TOKEN", "")
    xoxc = os.environ.get("SLACK_MCP_XOXC_TOKEN", "")
    xoxd = os.environ.get("SLACK_MCP_XOXD_TOKEN", "")

    if xoxp:
        token = xoxp
        is_bot = False
        xoxd_cookie = ""
    elif xoxb:
        token = xoxb
        is_bot = True
        xoxd_cookie = ""
    elif xoxc and xoxd:
        token = xoxc
        is_bot = False
        xoxd_cookie = xoxd
    elif xoxc or xoxd:
        print(
            "Fatal: SLACK_MCP_XOXC_TOKEN and SLACK_MCP_XOXD_TOKEN must both be set for cookie auth",
            file=sys.stderr,
        )
        sys.exit(1)
    else:
        print(
            "Fatal: set SLACK_MCP_XOXP_TOKEN, SLACK_MCP_XOXB_TOKEN, or both SLACK_MCP_XOXC_TOKEN and SLACK_MCP_XOXD_TOKEN",
            file=sys.stderr,
        )
        sys.exit(1)

    add_message_tool = os.environ.get("SLACK_MCP_ADD_MESSAGE_TOOL", "")
    validate_tool_config(add_message_tool, "SLACK_MCP_ADD_MESSAGE_TOOL")

    reaction_tool = os.environ.get("SLACK_MCP_REACTION_TOOL", "")
    validate_tool_config(reaction_tool, "SLACK_MCP_REACTION_TOOL")

    cache_ttl = _parse_cache_ttl(os.environ.get("SLACK_MCP_CACHE_TTL", ""))

    mark_env = os.environ.get("SLACK_MCP_ADD_MESSAGE_MARK", "")
    add_message_mark = mark_env in ("true", "1", "yes")

    cache_dir = _get_cache_dir()

    users_cache = os.environ.get(
        "SLACK_MCP_USERS_CACHE",
        os.path.join(cache_dir, "users_cache.json") if cache_dir else "",
    )
    channels_cache = os.environ.get(
        "SLACK_MCP_CHANNELS_CACHE",
        os.path.join(cache_dir, "channels_cache.json") if cache_dir else "",
    )

    return Config(
        token=token,
        is_bot_token=is_bot,
        xoxd_cookie=xoxd_cookie,
        log_level=os.environ.get("SLACK_MCP_LOG_LEVEL", "info").lower(),
        add_message_tool=add_message_tool,
        reaction_tool=reaction_tool,
        attachment_tool=os.environ.get("SLACK_MCP_ATTACHMENT_TOOL", ""),
        cache_ttl_seconds=cache_ttl,
        users_cache_path=users_cache,
        channels_cache_path=channels_cache,
        add_message_mark=add_message_mark,
        add_message_unfurling=os.environ.get("SLACK_MCP_ADD_MESSAGE_UNFURLING", ""),
    )


def validate_tool_config(config: str, env_name: str) -> None:
    if config == "" or config in ("true", "1"):
        return

    items = config.split(",")
    has_negated = False
    has_positive = False

    for item in items:
        item = item.strip()
        if not item:
            continue
        if item.startswith("!"):
            has_negated = True
        else:
            has_positive = True

    if has_negated and has_positive:
        print(
            f"Fatal: {env_name}: cannot mix allowed and disallowed (! prefixed) channels",
            file=sys.stderr,
        )
        sys.exit(1)


def is_channel_allowed(channel_id: str, config: str) -> bool:
    if config == "" or config in ("true", "1"):
        return True

    items = config.split(",")
    is_negated = items[0].strip().startswith("!")

    for item in items:
        item = item.strip()
        if is_negated:
            if item.lstrip("!") == channel_id:
                return False
        else:
            if item == channel_id:
                return True

    return is_negated


def _parse_cache_ttl(val: str) -> int:
    if not val:
        return 3600

    # Try as plain integer (seconds)
    try:
        secs = int(val)
        return max(secs, 0)
    except ValueError:
        pass

    # Try as duration string like "1h", "30m", "3600s"
    try:
        if val.endswith("h"):
            return int(val[:-1]) * 3600
        if val.endswith("m"):
            return int(val[:-1]) * 60
        if val.endswith("s"):
            return int(val[:-1])
    except ValueError:
        pass

    return 3600


def _get_cache_dir() -> str:
    cache_home = os.environ.get("XDG_CACHE_HOME", "")
    if not cache_home:
        cache_home = os.path.join(os.path.expanduser("~"), ".cache")
    cache_dir = os.path.join(cache_home, "slack-fast-mcp")
    try:
        os.makedirs(cache_dir, exist_ok=True)
    except OSError:
        return ""
    return cache_dir
