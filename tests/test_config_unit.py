from __future__ import annotations

import pytest

from slack_fast_mcp.config import is_channel_allowed, load_config, validate_tool_config


class TestIsChannelAllowedUnit:
    def test_empty_config_allows_all(self):
        assert is_channel_allowed("C123", "") is True

    def test_true_allows_all(self):
        assert is_channel_allowed("C123", "true") is True

    def test_one_allows_all(self):
        assert is_channel_allowed("C123", "1") is True

    def test_allowlist_match(self):
        assert is_channel_allowed("C001", "C001,C002") is True

    def test_allowlist_no_match(self):
        assert is_channel_allowed("C003", "C001,C002") is False

    def test_blocklist_match(self):
        assert is_channel_allowed("C001", "!C001,!C002") is False

    def test_blocklist_no_match(self):
        assert is_channel_allowed("C003", "!C001,!C002") is True

    def test_allowlist_with_spaces(self):
        assert is_channel_allowed("C002", "C001, C002") is True

    def test_blocklist_with_spaces(self):
        assert is_channel_allowed("C001", "!C001, !C002") is False


class TestValidateToolConfigUnit:
    def test_empty_passes(self):
        validate_tool_config("", "TEST")

    def test_true_passes(self):
        validate_tool_config("true", "TEST")

    def test_one_passes(self):
        validate_tool_config("1", "TEST")

    def test_allowlist_passes(self):
        validate_tool_config("C001,C002", "TEST")

    def test_blocklist_passes(self):
        validate_tool_config("!C001,!C002", "TEST")

    def test_mixed_fails(self):
        with pytest.raises(SystemExit):
            validate_tool_config("C001,!C002", "TEST")


class TestLoadConfigTokenPriorityUnit:
    def test_xoxp_takes_priority(self, monkeypatch):
        monkeypatch.setenv("SLACK_MCP_XOXP_TOKEN", "xoxp-123")
        monkeypatch.setenv("SLACK_MCP_XOXB_TOKEN", "xoxb-456")
        monkeypatch.setenv("SLACK_MCP_XOXC_TOKEN", "xoxc-789")
        monkeypatch.setenv("SLACK_MCP_XOXD_TOKEN", "xoxd-abc")
        cfg = load_config()
        assert cfg.token == "xoxp-123"
        assert cfg.is_bot_token is False
        assert cfg.xoxd_cookie == ""

    def test_xoxb_second_priority(self, monkeypatch):
        monkeypatch.delenv("SLACK_MCP_XOXP_TOKEN", raising=False)
        monkeypatch.setenv("SLACK_MCP_XOXB_TOKEN", "xoxb-456")
        monkeypatch.setenv("SLACK_MCP_XOXC_TOKEN", "xoxc-789")
        monkeypatch.setenv("SLACK_MCP_XOXD_TOKEN", "xoxd-abc")
        cfg = load_config()
        assert cfg.token == "xoxb-456"
        assert cfg.is_bot_token is True
        assert cfg.xoxd_cookie == ""

    def test_xoxc_xoxd_cookie_auth(self, monkeypatch):
        monkeypatch.delenv("SLACK_MCP_XOXP_TOKEN", raising=False)
        monkeypatch.delenv("SLACK_MCP_XOXB_TOKEN", raising=False)
        monkeypatch.setenv("SLACK_MCP_XOXC_TOKEN", "xoxc-789")
        monkeypatch.setenv("SLACK_MCP_XOXD_TOKEN", "xoxd-abc")
        cfg = load_config()
        assert cfg.token == "xoxc-789"
        assert cfg.is_bot_token is False
        assert cfg.xoxd_cookie == "xoxd-abc"

    def test_xoxc_without_xoxd_fails(self, monkeypatch):
        monkeypatch.delenv("SLACK_MCP_XOXP_TOKEN", raising=False)
        monkeypatch.delenv("SLACK_MCP_XOXB_TOKEN", raising=False)
        monkeypatch.setenv("SLACK_MCP_XOXC_TOKEN", "xoxc-789")
        monkeypatch.delenv("SLACK_MCP_XOXD_TOKEN", raising=False)
        with pytest.raises(SystemExit):
            load_config()

    def test_xoxd_without_xoxc_fails(self, monkeypatch):
        monkeypatch.delenv("SLACK_MCP_XOXP_TOKEN", raising=False)
        monkeypatch.delenv("SLACK_MCP_XOXB_TOKEN", raising=False)
        monkeypatch.delenv("SLACK_MCP_XOXC_TOKEN", raising=False)
        monkeypatch.setenv("SLACK_MCP_XOXD_TOKEN", "xoxd-abc")
        with pytest.raises(SystemExit):
            load_config()

    def test_no_tokens_fails(self, monkeypatch):
        monkeypatch.delenv("SLACK_MCP_XOXP_TOKEN", raising=False)
        monkeypatch.delenv("SLACK_MCP_XOXB_TOKEN", raising=False)
        monkeypatch.delenv("SLACK_MCP_XOXC_TOKEN", raising=False)
        monkeypatch.delenv("SLACK_MCP_XOXD_TOKEN", raising=False)
        with pytest.raises(SystemExit):
            load_config()
