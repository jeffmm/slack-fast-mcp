from __future__ import annotations

import os
import tempfile


from slack_fast_mcp.cache import Cache, ChannelsCache, UsersCache


class TestCacheUnit:
    def test_resolve_channel_id_found(self, populated_cache):
        assert populated_cache.resolve_channel_id("#general") == "C001"

    def test_resolve_channel_id_not_found(self, populated_cache):
        assert populated_cache.resolve_channel_id("#nonexistent") is None

    def test_resolve_dm_channel(self, populated_cache):
        assert populated_cache.resolve_channel_id("@alice") == "D001"

    def test_users_data(self, populated_cache):
        assert "U001" in populated_cache.users.users
        assert populated_cache.users.users_inv["alice"] == "U001"

    def test_channels_data(self, populated_cache):
        assert "C001" in populated_cache.channels.channels
        assert populated_cache.channels.channels["C001"].name == "#general"

    def test_is_ready(self, populated_cache):
        assert populated_cache.is_ready is True

    def test_not_ready_by_default(self, mock_client):
        cache = Cache(mock_client)
        assert cache.is_ready is False


class TestCacheDiskPersistenceUnit:
    def test_save_and_load_users(self, mock_client, sample_users):
        with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as f:
            path = f.name

        try:
            cache = Cache(mock_client, users_cache_path=path)
            users_inv = {u["name"]: uid for uid, u in sample_users.items()}
            cache._users = UsersCache(users=sample_users, users_inv=users_inv)
            cache._save_users_to_disk()

            # Load from disk
            cache2 = Cache(mock_client, users_cache_path=path)
            assert cache2._try_load_users_from_disk() is True
            assert "U001" in cache2._users.users
            assert cache2._users.users_inv["alice"] == "U001"
        finally:
            os.unlink(path)

    def test_save_and_load_channels(self, mock_client, sample_channels):
        with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as f:
            path = f.name

        try:
            cache = Cache(mock_client, channels_cache_path=path)
            channels_inv = {ch.name: cid for cid, ch in sample_channels.items()}
            cache._channels = ChannelsCache(
                channels=sample_channels, channels_inv=channels_inv
            )
            cache._save_channels_to_disk()

            # Load from disk
            cache2 = Cache(mock_client, channels_cache_path=path)
            assert cache2._try_load_channels_from_disk() is True
            assert "C001" in cache2._channels.channels
            assert cache2._channels.channels["C001"].name == "#general"
        finally:
            os.unlink(path)

    def test_ttl_expired(self, mock_client, sample_users):
        with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as f:
            path = f.name

        try:
            cache = Cache(mock_client, users_cache_path=path, ttl_seconds=0)
            users_inv = {u["name"]: uid for uid, u in sample_users.items()}
            cache._users = UsersCache(users=sample_users, users_inv=users_inv)
            cache._save_users_to_disk()

            # TTL=0 means cache forever, so should load
            cache2 = Cache(mock_client, users_cache_path=path, ttl_seconds=0)
            assert cache2._try_load_users_from_disk() is True
        finally:
            os.unlink(path)
