from __future__ import annotations

import base64
import json
from datetime import datetime, timezone

import pytest

from slack_fast_mcp.tools.search import (
    build_date_filters,
    build_query,
    conversations_search_messages,
    parse_flexible_date,
    split_query,
)


class TestSplitQueryUnit:
    def test_free_text_only(self):
        free, filters = split_query("hello world")
        assert free == ["hello", "world"]
        assert filters == {}

    def test_filters_only(self):
        free, filters = split_query("in:#general from:@alice")
        assert free == []
        assert filters["in"] == ["#general"]
        assert filters["from"] == ["@alice"]

    def test_mixed(self):
        free, filters = split_query("search term is:thread in:#random")
        assert free == ["search", "term"]
        assert filters["is"] == ["thread"]
        assert filters["in"] == ["#random"]

    def test_unknown_filter_treated_as_text(self):
        free, filters = split_query("unknown:value")
        assert free == ["unknown:value"]
        assert filters == {}


class TestBuildQueryUnit:
    def test_free_text_and_filters(self):
        result = build_query(
            ["hello"],
            {"in": ["#general"], "from": ["@alice"]},
        )
        assert result == "hello in:#general from:@alice"

    def test_preserves_order(self):
        result = build_query(
            [],
            {"after": ["2024-01-01"], "before": ["2024-12-31"]},
        )
        assert "before:2024-12-31" in result
        assert "after:2024-01-01" in result

    def test_empty(self):
        assert build_query([], {}) == ""


class TestParseFlexibleDateUnit:
    def test_standard_yyyy_mm_dd(self):
        assert parse_flexible_date("2024-01-15") == "2024-01-15"

    def test_standard_slash(self):
        assert parse_flexible_date("2024/01/15") == "2024-01-15"

    def test_month_day_year(self):
        assert parse_flexible_date("Jan 15, 2024") == "2024-01-15"

    def test_month_year(self):
        assert parse_flexible_date("January 2024") == "2024-01-01"

    def test_year_month(self):
        assert parse_flexible_date("2024 January") == "2024-01-01"

    def test_today(self):
        result = parse_flexible_date("today")
        expected = datetime.now(tz=timezone.utc).strftime("%Y-%m-%d")
        assert result == expected

    def test_yesterday(self):
        result = parse_flexible_date("yesterday")
        from datetime import timedelta

        expected = (datetime.now(tz=timezone.utc) - timedelta(days=1)).strftime(
            "%Y-%m-%d"
        )
        assert result == expected

    def test_days_ago(self):
        result = parse_flexible_date("7 days ago")
        from datetime import timedelta

        expected = (datetime.now(tz=timezone.utc) - timedelta(days=7)).strftime(
            "%Y-%m-%d"
        )
        assert result == expected

    def test_invalid_date(self):
        with pytest.raises(ValueError, match="unable to parse date"):
            parse_flexible_date("not a date")


class TestBuildDateFiltersUnit:
    def test_on_date(self):
        result = build_date_filters("", "", "2024-01-15", "")
        assert result == {"on": "2024-01-15"}

    def test_on_with_before_fails(self):
        with pytest.raises(ValueError, match="cannot be combined"):
            build_date_filters("2024-01-20", "", "2024-01-15", "")

    def test_during(self):
        result = build_date_filters("", "", "", "January 2024")
        assert result == {"during": "2024-01-01"}

    def test_during_with_before_fails(self):
        with pytest.raises(ValueError, match="cannot be combined"):
            build_date_filters("2024-01-20", "", "", "January 2024")

    def test_before_and_after(self):
        result = build_date_filters("2024-12-31", "2024-01-01", "", "")
        assert result == {"before": "2024-12-31", "after": "2024-01-01"}

    def test_after_after_before_fails(self):
        with pytest.raises(ValueError, match="after.*before"):
            build_date_filters("2024-01-01", "2024-12-31", "", "")

    def test_empty(self):
        assert build_date_filters("", "", "", "") == {}


class TestSearchUnit:
    @pytest.mark.asyncio
    async def test_basic_search(self, mock_client, populated_cache):
        mock_client.search_messages.return_value = {
            "messages": {
                "matches": [
                    {
                        "ts": "1234567890.123456",
                        "user": "U001",
                        "username": "alice",
                        "text": "Found message",
                        "channel": {"name": "general"},
                        "permalink": "https://team.slack.com/archives/C001/p1234567890123456",
                    }
                ],
                "pagination": {"page": 1, "page_count": 1},
            }
        }

        result = await conversations_search_messages(
            mock_client,
            populated_cache,
            search_query="hello",
        )
        data = json.loads(result)
        assert len(data) == 1
        assert "[SLACK_CONTENT]" in data[0]["text"]
        assert data[0]["channelID"] == "#general"

    @pytest.mark.asyncio
    async def test_search_with_pagination(self, mock_client, populated_cache):
        mock_client.search_messages.return_value = {
            "messages": {
                "matches": [
                    {
                        "ts": "1234567890.123456",
                        "user": "U001",
                        "text": "msg",
                        "channel": {"name": "general"},
                        "permalink": "",
                    }
                ],
                "pagination": {"page": 1, "page_count": 3},
            }
        }

        result = await conversations_search_messages(
            mock_client, populated_cache, search_query="test"
        )
        data = json.loads(result)
        assert data[0]["cursor"] != ""
        # Decode cursor
        decoded = base64.b64decode(data[0]["cursor"]).decode()
        assert decoded == "page:2"

    @pytest.mark.asyncio
    async def test_search_with_cursor(self, mock_client, populated_cache):
        cursor = base64.b64encode(b"page:2").decode()
        mock_client.search_messages.return_value = {
            "messages": {
                "matches": [],
                "pagination": {"page": 2, "page_count": 2},
            }
        }

        result = await conversations_search_messages(
            mock_client, populated_cache, search_query="test", cursor=cursor
        )
        data = json.loads(result)
        assert data == []
        mock_client.search_messages.assert_called_once()
        assert mock_client.search_messages.call_args.kwargs["page"] == 2
