from __future__ import annotations

import json

import pytest

from slack_fast_mcp.tools.users import users_search


class TestUsersSearchUnit:
    @pytest.mark.asyncio
    async def test_search_by_name(self, populated_cache):
        result = await users_search(populated_cache, query="alice")
        data = json.loads(result)
        assert len(data) == 1
        assert data[0]["userID"] == "U001"
        assert "[SLACK_CONTENT]" in data[0]["userName"]

    @pytest.mark.asyncio
    async def test_search_by_email(self, populated_cache):
        result = await users_search(populated_cache, query="bob@example.com")
        data = json.loads(result)
        assert len(data) == 1
        assert data[0]["userID"] == "U002"

    @pytest.mark.asyncio
    async def test_search_case_insensitive(self, populated_cache):
        result = await users_search(populated_cache, query="ALICE")
        data = json.loads(result)
        assert len(data) == 1

    @pytest.mark.asyncio
    async def test_search_skips_deleted(self, populated_cache):
        result = await users_search(populated_cache, query="charlie")
        assert result == "No users found matching the query."

    @pytest.mark.asyncio
    async def test_search_no_results(self, populated_cache):
        result = await users_search(populated_cache, query="nonexistent")
        assert result == "No users found matching the query."

    @pytest.mark.asyncio
    async def test_search_limit(self, populated_cache):
        result = await users_search(populated_cache, query="example.com", limit=1)
        data = json.loads(result)
        assert len(data) == 1

    @pytest.mark.asyncio
    async def test_search_dm_channel(self, populated_cache):
        result = await users_search(populated_cache, query="alice")
        data = json.loads(result)
        assert data[0]["dmChannelID"] == "D001"

    @pytest.mark.asyncio
    async def test_search_empty_query(self, populated_cache):
        with pytest.raises(ValueError, match="query is required"):
            await users_search(populated_cache, query="")
