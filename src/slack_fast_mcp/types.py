from __future__ import annotations

from pydantic import BaseModel, Field


class Message(BaseModel):
    msg_id: str = Field(alias="msgID")
    user_id: str = Field(alias="userID")
    user_name: str = Field(alias="userName")
    real_name: str = Field(alias="realName")
    channel: str = Field(alias="channelID")
    thread_ts: str = Field(default="", alias="threadTs")
    text: str = Field(alias="text")
    time: str = Field(alias="time")
    reactions: str = Field(default="", alias="reactions")
    bot_name: str = Field(default="", alias="botName")
    file_count: int = Field(default=0, alias="fileCount")
    attachment_ids: str = Field(default="", alias="attachmentIDs")
    has_media: bool = Field(default=False, alias="hasMedia")
    cursor: str = Field(default="", alias="cursor")

    model_config = {"populate_by_name": True}


class ChannelInfo(BaseModel):
    id: str = Field(alias="id")
    name: str = Field(alias="name")
    topic: str = Field(default="", alias="topic")
    purpose: str = Field(default="", alias="purpose")
    member_count: int = Field(default=0, alias="memberCount")
    cursor: str = Field(default="", alias="cursor")

    model_config = {"populate_by_name": True}


class UserInfo(BaseModel):
    user_id: str = Field(alias="userID")
    user_name: str = Field(alias="userName")
    real_name: str = Field(alias="realName")

    model_config = {"populate_by_name": True}


class UserSearchResult(BaseModel):
    user_id: str = Field(alias="userID")
    user_name: str = Field(alias="userName")
    real_name: str = Field(alias="realName")
    display_name: str = Field(default="", alias="displayName")
    email: str = Field(default="", alias="email")
    title: str = Field(default="", alias="title")
    dm_channel_id: str = Field(default="", alias="dmChannelID")

    model_config = {"populate_by_name": True}


class AttachmentResult(BaseModel):
    file_id: str = Field(alias="file_id")
    filename: str = Field(alias="filename")
    mimetype: str = Field(alias="mimetype")
    size: int = Field(alias="size")
    encoding: str = Field(alias="encoding")
    content: str = Field(alias="content")

    model_config = {"populate_by_name": True}
