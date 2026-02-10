from __future__ import annotations

import base64
import json
import logging

from fastmcp import Context

from slack_fast_mcp.config import Config
from slack_fast_mcp.sanitize import wrap_slack_content
from slack_fast_mcp.server import mcp
from slack_fast_mcp.slack_client import SlackClient
from slack_fast_mcp.types import AttachmentResult

logger = logging.getLogger(__name__)

MAX_FILE_SIZE_BYTES = 5 * 1024 * 1024  # 5MB

TEXT_MIMETYPES = {
    "application/json",
    "application/xml",
    "application/javascript",
    "application/x-yaml",
    "application/x-sh",
}


async def attachment_get_data(
    client: SlackClient,
    config: Config,
    *,
    file_id: str,
) -> str:
    tool_config = config.attachment_tool
    if not tool_config:
        raise ValueError(
            "by default, the attachment_get_data tool is disabled. "
            "To enable it, set the SLACK_MCP_ATTACHMENT_TOOL environment variable to true or 1"
        )
    if tool_config not in ("true", "1", "yes"):
        raise ValueError(
            "SLACK_MCP_ATTACHMENT_TOOL must be set to 'true', '1', or 'yes' to enable"
        )

    if not file_id:
        raise ValueError("file_id is required")

    resp = await client.files_info(file=file_id)
    file_info = resp.get("file", {})

    file_size = file_info.get("size", 0)
    if file_size > MAX_FILE_SIZE_BYTES:
        raise ValueError(
            f"file size {file_size} bytes exceeds maximum allowed size of {MAX_FILE_SIZE_BYTES} bytes"
        )

    mimetype = file_info.get("mimetype", "")
    filename = file_info.get("name", "")

    # For the Python version, we use the url_private_download or url_private
    # Since slack_sdk doesn't have a direct file download method that returns bytes,
    # we'll use the file content if available, or indicate the download URL
    download_url = file_info.get("url_private_download") or file_info.get("url_private")
    if not download_url:
        raise ValueError("file has no downloadable URL")

    # Use aiohttp to download the file content
    import aiohttp

    async with aiohttp.ClientSession() as session:
        headers = {"Authorization": f"Bearer {client._client.token}"}
        async with session.get(download_url, headers=headers) as resp_dl:
            if resp_dl.status != 200:
                raise ValueError(f"failed to download file: HTTP {resp_dl.status}")
            content = await resp_dl.read()

    encoding = "none"
    if _is_text_mimetype(mimetype):
        content_str = wrap_slack_content(content.decode("utf-8", errors="replace"))
    else:
        content_str = base64.b64encode(content).decode()
        encoding = "base64"

    result = AttachmentResult(
        file_id=file_info.get("id", file_id),
        filename=filename,
        mimetype=mimetype,
        size=len(content),
        encoding=encoding,
        content=content_str,
    )

    return json.dumps(result.model_dump(by_alias=True), ensure_ascii=False)


def _is_text_mimetype(mimetype: str) -> bool:
    if mimetype.startswith("text/"):
        return True
    return mimetype in TEXT_MIMETYPES


# --- MCP tool wrapper ---


@mcp.tool(
    name="attachment_get_data",
    description=(
        "Download an attachment's content by file ID. Returns file metadata and content "
        "(text files as-is, binary files as base64). Maximum file size is 5MB."
    ),
)
async def tool_attachment_get_data(
    file_id: str,
    ctx: Context = None,
) -> str:
    """Get attachment data.

    Args:
        file_id: The ID of the attachment (Fxxxxxxxxxx).
    """
    app_ctx = ctx.request_context.lifespan_context
    return await attachment_get_data(
        app_ctx["client"],
        app_ctx["config"],
        file_id=file_id,
    )
