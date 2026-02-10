from __future__ import annotations

import pytest

from slack_fast_mcp.config import Config
from slack_fast_mcp.tools.reactions import reactions_add, reactions_remove


class TestReactionsAddUnit:
    @pytest.mark.asyncio
    async def test_disabled_by_default(
        self, mock_client, populated_cache, default_config
    ):
        with pytest.raises(ValueError, match="disabled"):
            await reactions_add(
                mock_client,
                populated_cache,
                default_config,
                channel_id="C001",
                timestamp="1234567890.123456",
                emoji="thumbsup",
            )

    @pytest.mark.asyncio
    async def test_add_reaction(
        self, mock_client, populated_cache, write_enabled_config
    ):
        mock_client.reactions_add.return_value = {"ok": True}

        result = await reactions_add(
            mock_client,
            populated_cache,
            write_enabled_config,
            channel_id="C001",
            timestamp="1234567890.123456",
            emoji="thumbsup",
        )
        assert "Successfully added" in result
        assert "thumbsup" in result

    @pytest.mark.asyncio
    async def test_strips_colons(
        self, mock_client, populated_cache, write_enabled_config
    ):
        mock_client.reactions_add.return_value = {"ok": True}

        result = await reactions_add(
            mock_client,
            populated_cache,
            write_enabled_config,
            channel_id="C001",
            timestamp="1234567890.123456",
            emoji=":heart:",
        )
        assert "heart" in result
        mock_client.reactions_add.assert_called_once_with(
            channel="C001", timestamp="1234567890.123456", name="heart"
        )

    @pytest.mark.asyncio
    async def test_channel_not_allowed(self, mock_client, populated_cache):
        config = Config(
            token="xoxp-test",
            is_bot_token=False,
            reaction_tool="C999",
        )
        with pytest.raises(ValueError, match="not allowed"):
            await reactions_add(
                mock_client,
                populated_cache,
                config,
                channel_id="C001",
                timestamp="1234567890.123456",
                emoji="thumbsup",
            )

    @pytest.mark.asyncio
    async def test_empty_emoji(
        self, mock_client, populated_cache, write_enabled_config
    ):
        with pytest.raises(ValueError, match="emoji is required"):
            await reactions_add(
                mock_client,
                populated_cache,
                write_enabled_config,
                channel_id="C001",
                timestamp="1234567890.123456",
                emoji="",
            )


class TestReactionsRemoveUnit:
    @pytest.mark.asyncio
    async def test_remove_reaction(
        self, mock_client, populated_cache, write_enabled_config
    ):
        mock_client.reactions_remove.return_value = {"ok": True}

        result = await reactions_remove(
            mock_client,
            populated_cache,
            write_enabled_config,
            channel_id="C001",
            timestamp="1234567890.123456",
            emoji="thumbsup",
        )
        assert "Successfully removed" in result

    @pytest.mark.asyncio
    async def test_disabled_by_default(
        self, mock_client, populated_cache, default_config
    ):
        with pytest.raises(ValueError, match="disabled"):
            await reactions_remove(
                mock_client,
                populated_cache,
                default_config,
                channel_id="C001",
                timestamp="1234567890.123456",
                emoji="thumbsup",
            )
