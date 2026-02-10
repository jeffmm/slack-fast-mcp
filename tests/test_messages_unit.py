from __future__ import annotations

import json

import pytest

from slack_fast_mcp.config import Config
from slack_fast_mcp.tools.messages import conversations_add_message


class TestConversationsAddMessageUnit:
    @pytest.mark.asyncio
    async def test_disabled_by_default(
        self, mock_client, populated_cache, default_config
    ):
        with pytest.raises(ValueError, match="disabled"):
            await conversations_add_message(
                mock_client,
                populated_cache,
                default_config,
                channel_id="C001",
                payload="hello",
            )

    @pytest.mark.asyncio
    async def test_send_message(
        self, mock_client, populated_cache, write_enabled_config
    ):
        mock_client.chat_post_message.return_value = {
            "channel": "C001",
            "ts": "1234567890.123456",
        }
        mock_client.conversations_history.return_value = {
            "messages": [
                {
                    "ts": "1234567890.123456",
                    "user": "U001",
                    "text": "hello",
                }
            ],
        }

        result = await conversations_add_message(
            mock_client,
            populated_cache,
            write_enabled_config,
            channel_id="C001",
            payload="hello",
        )
        data = json.loads(result)
        assert len(data) == 1
        assert "[SLACK_CONTENT]" in data[0]["text"]

    @pytest.mark.asyncio
    async def test_channel_not_allowed(self, mock_client, populated_cache):
        config = Config(
            token="xoxp-test",
            is_bot_token=False,
            add_message_tool="C999",  # Only C999 allowed
        )
        with pytest.raises(ValueError, match="not allowed"):
            await conversations_add_message(
                mock_client,
                populated_cache,
                config,
                channel_id="C001",
                payload="hello",
            )

    @pytest.mark.asyncio
    async def test_empty_payload(
        self, mock_client, populated_cache, write_enabled_config
    ):
        with pytest.raises(ValueError, match="text must be a string"):
            await conversations_add_message(
                mock_client,
                populated_cache,
                write_enabled_config,
                channel_id="C001",
                payload="",
            )

    @pytest.mark.asyncio
    async def test_invalid_thread_ts(
        self, mock_client, populated_cache, write_enabled_config
    ):
        with pytest.raises(ValueError, match="thread_ts must be a valid"):
            await conversations_add_message(
                mock_client,
                populated_cache,
                write_enabled_config,
                channel_id="C001",
                payload="hello",
                thread_ts="invalid",
            )

    @pytest.mark.asyncio
    async def test_invalid_content_type(
        self, mock_client, populated_cache, write_enabled_config
    ):
        with pytest.raises(ValueError, match="content_type"):
            await conversations_add_message(
                mock_client,
                populated_cache,
                write_enabled_config,
                channel_id="C001",
                payload="hello",
                content_type="text/html",
            )
