from __future__ import annotations

import time

from slack_sdk.http_retry.builtin_async_handlers import AsyncRateLimitErrorRetryHandler
from slack_sdk.web.async_client import AsyncWebClient


_BROWSER_USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"
)


class SlackClient:
    def __init__(self, token: str, cookie: str = "") -> None:
        headers: dict[str, str] = {}
        if cookie:
            headers["cookie"] = f"d={cookie}; d-s={int(time.time()) - 10}"
            headers["User-Agent"] = _BROWSER_USER_AGENT
        self._client = AsyncWebClient(token=token, headers=headers)
        self._client.retry_handlers.append(AsyncRateLimitErrorRetryHandler(max_retry_count=3))

    async def auth_test(self) -> dict:
        resp = await self._client.auth_test()
        return resp.data

    async def conversations_history(
        self,
        *,
        channel: str,
        limit: int = 100,
        oldest: str = "",
        latest: str = "",
        cursor: str = "",
        inclusive: bool = False,
    ) -> dict:
        kwargs: dict = {"channel": channel, "limit": limit, "inclusive": inclusive}
        if oldest:
            kwargs["oldest"] = oldest
        if latest:
            kwargs["latest"] = latest
        if cursor:
            kwargs["cursor"] = cursor
        resp = await self._client.conversations_history(**kwargs)
        return resp.data

    async def conversations_replies(
        self,
        *,
        channel: str,
        ts: str,
        limit: int = 100,
        oldest: str = "",
        latest: str = "",
        cursor: str = "",
        inclusive: bool = False,
    ) -> dict:
        kwargs: dict = {
            "channel": channel,
            "ts": ts,
            "limit": limit,
            "inclusive": inclusive,
        }
        if oldest:
            kwargs["oldest"] = oldest
        if latest:
            kwargs["latest"] = latest
        if cursor:
            kwargs["cursor"] = cursor
        resp = await self._client.conversations_replies(**kwargs)
        return resp.data

    async def search_messages(
        self, *, query: str, count: int = 20, page: int = 1
    ) -> dict:
        resp = await self._client.search_messages(
            query=query, count=count, page=page, sort="timestamp", sort_dir="desc"
        )
        return resp.data

    async def conversations_list(
        self,
        *,
        types: str = "public_channel",
        limit: int = 200,
        cursor: str = "",
    ) -> dict:
        kwargs: dict = {"types": types, "limit": limit}
        if cursor:
            kwargs["cursor"] = cursor
        resp = await self._client.conversations_list(**kwargs)
        return resp.data

    async def users_list(self, *, cursor: str = "", limit: int = 200) -> dict:
        kwargs: dict = {"limit": limit}
        if cursor:
            kwargs["cursor"] = cursor
        resp = await self._client.users_list(**kwargs)
        return resp.data

    async def chat_post_message(
        self,
        *,
        channel: str,
        text: str = "",
        thread_ts: str = "",
        mrkdwn: bool = True,
        unfurl_links: bool = False,
        unfurl_media: bool = False,
    ) -> dict:
        kwargs: dict = {
            "channel": channel,
            "text": text,
            "mrkdwn": mrkdwn,
            "unfurl_links": unfurl_links,
            "unfurl_media": unfurl_media,
        }
        if thread_ts:
            kwargs["thread_ts"] = thread_ts
        resp = await self._client.chat_postMessage(**kwargs)
        return resp.data

    async def reactions_add(self, *, channel: str, timestamp: str, name: str) -> dict:
        resp = await self._client.reactions_add(
            channel=channel, timestamp=timestamp, name=name
        )
        return resp.data

    async def reactions_remove(
        self, *, channel: str, timestamp: str, name: str
    ) -> dict:
        resp = await self._client.reactions_remove(
            channel=channel, timestamp=timestamp, name=name
        )
        return resp.data

    async def files_info(self, *, file: str) -> dict:
        resp = await self._client.files_info(file=file)
        return resp.data

    async def conversations_mark(self, *, channel: str, ts: str) -> dict:
        resp = await self._client.conversations_mark(channel=channel, ts=ts)
        return resp.data
