from __future__ import annotations

import json

import pytest

from slack_fast_mcp.tools.channels import channels_list


class TestChannelsListUnit:
    @pytest.mark.asyncio
    async def test_list_public_channels(self, populated_cache):
        result = await channels_list(populated_cache, channel_types="public_channel")
        data = json.loads(result)
        names = [ch["name"] for ch in data]
        assert "#general" in names
        assert "#random" in names
        # Private channel should not be included
        assert "#private-channel" not in names

    @pytest.mark.asyncio
    async def test_list_private_channels(self, populated_cache):
        result = await channels_list(populated_cache, channel_types="private_channel")
        data = json.loads(result)
        names = [ch["name"] for ch in data]
        assert "#private-channel" in names
        assert "#general" not in names

    @pytest.mark.asyncio
    async def test_list_im(self, populated_cache):
        result = await channels_list(populated_cache, channel_types="im")
        data = json.loads(result)
        assert len(data) == 1
        assert data[0]["name"] == "@alice"

    @pytest.mark.asyncio
    async def test_list_mpim(self, populated_cache):
        result = await channels_list(populated_cache, channel_types="mpim")
        data = json.loads(result)
        assert len(data) == 1

    @pytest.mark.asyncio
    async def test_list_multiple_types(self, populated_cache):
        result = await channels_list(
            populated_cache, channel_types="public_channel,private_channel"
        )
        data = json.loads(result)
        assert len(data) == 3  # general + random + private

    @pytest.mark.asyncio
    async def test_popularity_sort(self, populated_cache):
        result = await channels_list(
            populated_cache,
            channel_types="public_channel",
            sort="popularity",
        )
        data = json.loads(result)
        assert data[0]["memberCount"] >= data[1]["memberCount"]

    @pytest.mark.asyncio
    async def test_pagination(self, populated_cache):
        result = await channels_list(
            populated_cache,
            channel_types="public_channel,private_channel",
            limit=1,
        )
        data = json.loads(result)
        assert len(data) == 1
        assert data[0]["cursor"] != ""

        # Use cursor for next page
        next_cursor = data[0]["cursor"]
        result2 = await channels_list(
            populated_cache,
            channel_types="public_channel,private_channel",
            limit=1,
            cursor=next_cursor,
        )
        data2 = json.loads(result2)
        assert len(data2) == 1
        assert data2[0]["id"] != data[0]["id"]

    @pytest.mark.asyncio
    async def test_limit_cap(self, populated_cache):
        result = await channels_list(
            populated_cache, channel_types="public_channel", limit=5000
        )
        data = json.loads(result)
        # Should not error, limit is capped to 999
        assert len(data) >= 1

    @pytest.mark.asyncio
    async def test_invalid_types_fallback(self, populated_cache):
        result = await channels_list(populated_cache, channel_types="invalid_type")
        data = json.loads(result)
        # Falls back to public + private
        assert len(data) >= 1

    @pytest.mark.asyncio
    async def test_sanitized_topic(self, populated_cache):
        result = await channels_list(populated_cache, channel_types="public_channel")
        data = json.loads(result)
        general = next(ch for ch in data if ch["name"] == "#general")
        assert "[SLACK_CONTENT]" in general["topic"]
