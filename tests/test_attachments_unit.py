from __future__ import annotations

import pytest

from slack_fast_mcp.config import Config
from slack_fast_mcp.tools.attachments import _is_text_mimetype, attachment_get_data


class TestIsTextMimetypeUnit:
    def test_text_plain(self):
        assert _is_text_mimetype("text/plain") is True

    def test_text_html(self):
        assert _is_text_mimetype("text/html") is True

    def test_application_json(self):
        assert _is_text_mimetype("application/json") is True

    def test_application_xml(self):
        assert _is_text_mimetype("application/xml") is True

    def test_image_png(self):
        assert _is_text_mimetype("image/png") is False

    def test_application_pdf(self):
        assert _is_text_mimetype("application/pdf") is False


class TestAttachmentGetDataUnit:
    @pytest.mark.asyncio
    async def test_disabled_by_default(self, mock_client, default_config):
        with pytest.raises(ValueError, match="disabled"):
            await attachment_get_data(
                mock_client,
                default_config,
                file_id="F123",
            )

    @pytest.mark.asyncio
    async def test_invalid_config_value(self, mock_client):
        config = Config(
            token="xoxp-test",
            is_bot_token=False,
            attachment_tool="maybe",
        )
        with pytest.raises(ValueError, match="must be set"):
            await attachment_get_data(
                mock_client,
                config,
                file_id="F123",
            )

    @pytest.mark.asyncio
    async def test_empty_file_id(self, mock_client, write_enabled_config):
        with pytest.raises(ValueError, match="file_id is required"):
            await attachment_get_data(
                mock_client,
                write_enabled_config,
                file_id="",
            )

    @pytest.mark.asyncio
    async def test_file_too_large(self, mock_client, write_enabled_config):
        mock_client.files_info.return_value = {
            "file": {
                "id": "F123",
                "name": "big.bin",
                "mimetype": "application/octet-stream",
                "size": 10 * 1024 * 1024,  # 10MB
                "url_private_download": "https://files.slack.com/files-pri/T0/big.bin",
            }
        }
        with pytest.raises(ValueError, match="exceeds maximum"):
            await attachment_get_data(
                mock_client,
                write_enabled_config,
                file_id="F123",
            )
