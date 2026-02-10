from __future__ import annotations

from unittest.mock import AsyncMock

import pytest

from slack_fast_mcp.cache import Cache, CachedChannel, ChannelsCache, UsersCache
from slack_fast_mcp.config import Config
from slack_fast_mcp.slack_client import SlackClient


@pytest.fixture
def mock_client():
    client = AsyncMock(spec=SlackClient)
    return client


@pytest.fixture
def sample_users():
    return {
        "U001": {
            "id": "U001",
            "name": "alice",
            "real_name": "Alice Smith",
            "deleted": False,
            "profile": {
                "display_name": "Alice S",
                "email": "alice@example.com",
                "title": "Engineer",
            },
        },
        "U002": {
            "id": "U002",
            "name": "bob",
            "real_name": "Bob Jones",
            "deleted": False,
            "profile": {
                "display_name": "Bob J",
                "email": "bob@example.com",
                "title": "Manager",
            },
        },
        "U003": {
            "id": "U003",
            "name": "charlie",
            "real_name": "Charlie Brown",
            "deleted": True,
            "profile": {
                "display_name": "Charlie",
                "email": "charlie@example.com",
                "title": "",
            },
        },
    }


@pytest.fixture
def sample_channels():
    return {
        "C001": CachedChannel(
            id="C001",
            name="#general",
            topic="General discussion",
            purpose="Company-wide channel",
            member_count=100,
        ),
        "C002": CachedChannel(
            id="C002",
            name="#random",
            topic="Random stuff",
            purpose="Non-work",
            member_count=50,
        ),
        "C003": CachedChannel(
            id="C003",
            name="#private-channel",
            topic="",
            purpose="",
            member_count=5,
            is_private=True,
        ),
        "D001": CachedChannel(
            id="D001",
            name="@alice",
            is_im=True,
            user="U001",
        ),
        "G001": CachedChannel(
            id="G001",
            name="@mpdm-alice--bob",
            is_mpim=True,
            member_count=2,
        ),
    }


@pytest.fixture
def populated_cache(mock_client, sample_users, sample_channels):
    cache = Cache(mock_client)

    users_inv = {u["name"]: uid for uid, u in sample_users.items()}
    cache._users = UsersCache(users=sample_users, users_inv=users_inv)
    cache._users_ready = True

    channels_inv = {ch.name: cid for cid, ch in sample_channels.items()}
    cache._channels = ChannelsCache(channels=sample_channels, channels_inv=channels_inv)
    cache._channels_ready = True

    return cache


@pytest.fixture
def default_config():
    return Config(
        token="xoxp-test-token",
        is_bot_token=False,
    )


@pytest.fixture
def write_enabled_config():
    return Config(
        token="xoxp-test-token",
        is_bot_token=False,
        add_message_tool="true",
        reaction_tool="true",
        attachment_tool="true",
    )
