from __future__ import annotations

import json

import pytest

from slack_fast_mcp.tools.conversations import (
    _limit_by_expression,
    _limit_by_numeric,
    conversations_history,
    conversations_replies,
)


class TestLimitParsingUnit:
    def test_numeric_default(self):
        assert _limit_by_numeric("") == 50

    def test_numeric_custom(self):
        assert _limit_by_numeric("25") == 25

    def test_numeric_invalid(self):
        with pytest.raises(ValueError, match="invalid numeric limit"):
            _limit_by_numeric("abc")

    def test_expression_1d(self):
        limit, oldest, latest = _limit_by_expression("1d")
        assert limit == 100
        assert oldest != ""
        assert latest != ""
        # oldest should be before latest
        assert float(oldest) < float(latest)

    def test_expression_1w(self):
        limit, oldest, latest = _limit_by_expression("1w")
        assert limit == 100
        assert float(oldest) < float(latest)

    def test_expression_1m(self):
        limit, oldest, latest = _limit_by_expression("1m")
        assert limit == 100
        assert float(oldest) < float(latest)

    def test_expression_invalid_suffix(self):
        with pytest.raises(ValueError):
            _limit_by_expression("1x")

    def test_expression_too_short(self):
        with pytest.raises(ValueError, match="too short"):
            _limit_by_expression("d")

    def test_expression_zero(self):
        with pytest.raises(ValueError, match="positive integer"):
            _limit_by_expression("0d")


class TestConversationsHistoryUnit:
    @pytest.mark.asyncio
    async def test_basic_history(self, mock_client, populated_cache):
        mock_client.conversations_history.return_value = {
            "messages": [
                {
                    "ts": "1234567890.123456",
                    "user": "U001",
                    "text": "Hello world",
                    "reactions": [{"name": "thumbsup", "count": 2}],
                }
            ],
            "has_more": False,
            "response_metadata": {"next_cursor": ""},
        }

        result = await conversations_history(
            mock_client, populated_cache, channel_id="C001"
        )
        data = json.loads(result)
        assert len(data) == 1
        assert "[SLACK_CONTENT]" in data[0]["text"]
        assert data[0]["reactions"] == "thumbsup:2"
        assert data[0]["cursor"] == ""

    @pytest.mark.asyncio
    async def test_history_with_pagination(self, mock_client, populated_cache):
        mock_client.conversations_history.return_value = {
            "messages": [
                {
                    "ts": "1234567890.123456",
                    "user": "U001",
                    "text": "Hello",
                }
            ],
            "has_more": True,
            "response_metadata": {"next_cursor": "next_page_cursor"},
        }

        result = await conversations_history(
            mock_client, populated_cache, channel_id="C001"
        )
        data = json.loads(result)
        assert data[0]["cursor"] == "next_page_cursor"

    @pytest.mark.asyncio
    async def test_history_filters_activity(self, mock_client, populated_cache):
        mock_client.conversations_history.return_value = {
            "messages": [
                {
                    "ts": "1234567890.123456",
                    "user": "U001",
                    "text": "Hello",
                },
                {
                    "ts": "1234567891.123456",
                    "user": "U001",
                    "text": "joined",
                    "subtype": "channel_join",
                },
            ],
            "has_more": False,
            "response_metadata": {"next_cursor": ""},
        }

        result = await conversations_history(
            mock_client,
            populated_cache,
            channel_id="C001",
            include_activity_messages=False,
        )
        data = json.loads(result)
        assert len(data) == 1

    @pytest.mark.asyncio
    async def test_history_includes_activity(self, mock_client, populated_cache):
        mock_client.conversations_history.return_value = {
            "messages": [
                {
                    "ts": "1234567890.123456",
                    "user": "U001",
                    "text": "Hello",
                },
                {
                    "ts": "1234567891.123456",
                    "user": "U001",
                    "text": "joined",
                    "subtype": "channel_join",
                },
            ],
            "has_more": False,
            "response_metadata": {"next_cursor": ""},
        }

        result = await conversations_history(
            mock_client,
            populated_cache,
            channel_id="C001",
            include_activity_messages=True,
        )
        data = json.loads(result)
        assert len(data) == 2

    @pytest.mark.asyncio
    async def test_history_resolves_channel_name(self, mock_client, populated_cache):
        mock_client.conversations_history.return_value = {
            "messages": [],
            "has_more": False,
            "response_metadata": {"next_cursor": ""},
        }

        result = await conversations_history(
            mock_client, populated_cache, channel_id="#general"
        )
        data = json.loads(result)
        assert data == []
        mock_client.conversations_history.assert_called_once()
        call_args = mock_client.conversations_history.call_args
        assert call_args.kwargs["channel"] == "C001"

    @pytest.mark.asyncio
    async def test_history_unknown_channel_name(self, mock_client, populated_cache):
        with pytest.raises(ValueError, match="not found"):
            await conversations_history(
                mock_client, populated_cache, channel_id="#nonexistent"
            )


class TestConversationsRepliesUnit:
    @pytest.mark.asyncio
    async def test_basic_replies(self, mock_client, populated_cache):
        mock_client.conversations_replies.return_value = {
            "messages": [
                {
                    "ts": "1234567890.123456",
                    "user": "U001",
                    "text": "Thread parent",
                    "thread_ts": "1234567890.123456",
                },
                {
                    "ts": "1234567891.123456",
                    "user": "U002",
                    "text": "Reply",
                    "thread_ts": "1234567890.123456",
                },
            ],
            "has_more": False,
            "response_metadata": {"next_cursor": ""},
        }

        result = await conversations_replies(
            mock_client,
            populated_cache,
            channel_id="C001",
            thread_ts="1234567890.123456",
        )
        data = json.loads(result)
        assert len(data) == 2
        assert data[0]["threadTs"] == "1234567890.123456"
