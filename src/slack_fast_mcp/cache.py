from __future__ import annotations

import json
import logging
import os
import time
from dataclasses import dataclass, field

from slack_fast_mcp.slack_client import SlackClient

logger = logging.getLogger(__name__)


@dataclass
class CachedChannel:
    id: str
    name: str
    topic: str = ""
    purpose: str = ""
    member_count: int = 0
    is_im: bool = False
    is_mpim: bool = False
    is_private: bool = False
    user: str = ""


@dataclass
class UsersCache:
    users: dict[str, dict] = field(default_factory=dict)
    users_inv: dict[str, str] = field(default_factory=dict)


@dataclass
class ChannelsCache:
    channels: dict[str, CachedChannel] = field(default_factory=dict)
    channels_inv: dict[str, str] = field(default_factory=dict)


class Cache:
    def __init__(
        self,
        client: SlackClient,
        *,
        ttl_seconds: int = 3600,
        users_cache_path: str = "",
        channels_cache_path: str = "",
    ) -> None:
        self._client = client
        self._ttl = ttl_seconds
        self._users_cache_path = users_cache_path
        self._channels_cache_path = channels_cache_path
        self._users = UsersCache()
        self._channels = ChannelsCache()
        self._users_ready = False
        self._channels_ready = False

    @property
    def users(self) -> UsersCache:
        return self._users

    @property
    def channels(self) -> ChannelsCache:
        return self._channels

    @property
    def is_ready(self) -> bool:
        return self._users_ready and self._channels_ready

    async def warm(self) -> None:
        await self.refresh_users()
        await self.refresh_channels()

    async def refresh_users(self, *, force: bool = False) -> None:
        if not force and self._try_load_users_from_disk():
            self._users_ready = True
            logger.info("Users cache loaded from disk")
            return

        logger.info("Fetching users from Slack API...")
        all_users: list[dict] = []
        cursor = ""
        while True:
            resp = await self._client.users_list(cursor=cursor, limit=200)
            members = resp.get("members", [])
            all_users.extend(members)
            cursor = resp.get("response_metadata", {}).get("next_cursor", "")
            if not cursor:
                break

        users_map: dict[str, dict] = {}
        users_inv: dict[str, str] = {}
        for u in all_users:
            uid = u.get("id", "")
            name = u.get("name", "")
            users_map[uid] = u
            if name:
                users_inv[name] = uid

        self._users = UsersCache(users=users_map, users_inv=users_inv)
        self._users_ready = True
        self._save_users_to_disk()
        logger.info("Users cache refreshed: %d users", len(users_map))

    async def refresh_channels(self, *, force: bool = False) -> None:
        if not force and self._try_load_channels_from_disk():
            self._channels_ready = True
            logger.info("Channels cache loaded from disk")
            return

        logger.info("Fetching channels from Slack API...")
        all_channels: list[dict] = []
        types_str = "public_channel,private_channel,im,mpim"
        cursor = ""
        while True:
            resp = await self._client.conversations_list(
                types=types_str, limit=200, cursor=cursor
            )
            channels = resp.get("channels", [])
            all_channels.extend(channels)
            cursor = resp.get("response_metadata", {}).get("next_cursor", "")
            if not cursor:
                break

        channels_map: dict[str, CachedChannel] = {}
        channels_inv: dict[str, str] = {}

        for ch in all_channels:
            cid = ch.get("id", "")
            is_im = ch.get("is_im", False)
            is_mpim = ch.get("is_mpim", False)
            is_private = ch.get("is_private", False)

            name = self._map_channel_name(ch, is_im, is_mpim)

            topic = (
                ch.get("topic", {}).get("value", "")
                if isinstance(ch.get("topic"), dict)
                else ""
            )
            purpose = (
                ch.get("purpose", {}).get("value", "")
                if isinstance(ch.get("purpose"), dict)
                else ""
            )

            cached = CachedChannel(
                id=cid,
                name=name,
                topic=topic,
                purpose=purpose,
                member_count=ch.get("num_members", 0),
                is_im=is_im,
                is_mpim=is_mpim,
                is_private=is_private,
                user=ch.get("user", ""),
            )
            channels_map[cid] = cached

            if name:
                channels_inv[name] = cid

        self._channels = ChannelsCache(channels=channels_map, channels_inv=channels_inv)
        self._channels_ready = True
        self._save_channels_to_disk()
        logger.info("Channels cache refreshed: %d channels", len(channels_map))

    def _map_channel_name(self, ch: dict, is_im: bool, is_mpim: bool) -> str:
        if is_im:
            user_id = ch.get("user", "")
            user_data = self._users.users.get(user_id)
            if user_data:
                return f"@{user_data.get('name', user_id)}"
            return f"@{user_id}"
        if is_mpim:
            raw_name = ch.get("name", "")
            return f"@{raw_name}"
        name = ch.get("name", "")
        return f"#{name}" if name else ""

    def resolve_channel_id(self, name: str) -> str | None:
        cid = self._channels.channels_inv.get(name)
        if cid:
            return cid
        return None

    def _try_load_users_from_disk(self) -> bool:
        if not self._users_cache_path:
            return False
        try:
            stat = os.stat(self._users_cache_path)
            if self._ttl > 0 and (time.time() - stat.st_mtime) > self._ttl:
                return False
            with open(self._users_cache_path) as f:
                data = json.load(f)
            users_map: dict[str, dict] = {}
            users_inv: dict[str, str] = {}
            for u in data:
                uid = u.get("id", "")
                name = u.get("name", "")
                users_map[uid] = u
                if name:
                    users_inv[name] = uid
            self._users = UsersCache(users=users_map, users_inv=users_inv)
            return True
        except (OSError, json.JSONDecodeError, KeyError):
            return False

    def _save_users_to_disk(self) -> None:
        if not self._users_cache_path:
            return
        try:
            os.makedirs(os.path.dirname(self._users_cache_path), exist_ok=True)
            data = list(self._users.users.values())
            with open(self._users_cache_path, "w") as f:
                json.dump(data, f)
        except OSError:
            logger.warning("Failed to save users cache to disk")

    def _try_load_channels_from_disk(self) -> bool:
        if not self._channels_cache_path:
            return False
        try:
            stat = os.stat(self._channels_cache_path)
            if self._ttl > 0 and (time.time() - stat.st_mtime) > self._ttl:
                return False
            with open(self._channels_cache_path) as f:
                data = json.load(f)
            channels_map: dict[str, CachedChannel] = {}
            channels_inv: dict[str, str] = {}
            for ch in data:
                cid = ch.get("id", "")
                cached = CachedChannel(
                    id=cid,
                    name=ch.get("name", ""),
                    topic=ch.get("topic", ""),
                    purpose=ch.get("purpose", ""),
                    member_count=ch.get("member_count", 0),
                    is_im=ch.get("is_im", False),
                    is_mpim=ch.get("is_mpim", False),
                    is_private=ch.get("is_private", False),
                    user=ch.get("user", ""),
                )
                channels_map[cid] = cached
                if cached.name:
                    channels_inv[cached.name] = cid
            self._channels = ChannelsCache(
                channels=channels_map, channels_inv=channels_inv
            )
            return True
        except (OSError, json.JSONDecodeError, KeyError):
            return False

    def _save_channels_to_disk(self) -> None:
        if not self._channels_cache_path:
            return
        try:
            os.makedirs(os.path.dirname(self._channels_cache_path), exist_ok=True)
            data = []
            for ch in self._channels.channels.values():
                data.append(
                    {
                        "id": ch.id,
                        "name": ch.name,
                        "topic": ch.topic,
                        "purpose": ch.purpose,
                        "member_count": ch.member_count,
                        "is_im": ch.is_im,
                        "is_mpim": ch.is_mpim,
                        "is_private": ch.is_private,
                        "user": ch.user,
                    }
                )
            with open(self._channels_cache_path, "w") as f:
                json.dump(data, f)
        except OSError:
            logger.warning("Failed to save channels cache to disk")
