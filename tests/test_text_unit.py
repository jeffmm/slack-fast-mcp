from __future__ import annotations

import pytest

from slack_fast_mcp.text import (
    attachment_to_text,
    attachments_to_text,
    blocks_to_text,
    process_text,
    timestamp_to_rfc3339,
    workspace_from_url,
)


class TestTimestampToRfc3339Unit:
    def test_valid_timestamp(self):
        result = timestamp_to_rfc3339("1234567890.123456")
        assert result == "2009-02-13T23:31:30Z"

    def test_invalid_no_dot(self):
        with pytest.raises(ValueError, match="invalid slack timestamp"):
            timestamp_to_rfc3339("1234567890")

    def test_invalid_multiple_dots(self):
        with pytest.raises(ValueError, match="invalid slack timestamp"):
            timestamp_to_rfc3339("123.456.789")


class TestWorkspaceFromUrlUnit:
    def test_standard_url(self):
        assert workspace_from_url("https://myteam.slack.com/") == "myteam"

    def test_with_path(self):
        assert workspace_from_url("https://team.slack.com/messages/C123") == "team"

    def test_too_few_parts(self):
        with pytest.raises(ValueError, match="invalid Slack URL"):
            workspace_from_url("https://localhost/")


class TestProcessTextUnit:
    def test_slack_link(self):
        result = process_text("<https://example.com|Click here>")
        assert "https://example.com - Click here" in result

    def test_markdown_link(self):
        result = process_text("[Click](https://example.com)")
        assert "https://example.com - Click" in result

    def test_preserves_urls(self):
        result = process_text("Visit https://example.com/path?q=1 now")
        assert "https://example.com/path?q=1" in result

    def test_removes_special_chars(self):
        result = process_text("Hello {world} <tag>")
        assert "{" not in result
        assert "}" not in result

    def test_collapses_whitespace(self):
        result = process_text("hello    world")
        assert result == "hello world"

    def test_empty_string(self):
        assert process_text("") == ""


class TestAttachmentToTextUnit:
    def test_full_attachment(self):
        att = {
            "title": "Report",
            "author_name": "Alice",
            "pretext": "Here is the report",
            "text": "Some content",
            "footer": "Bot",
            "ts": "1234567890",
        }
        result = attachment_to_text(att)
        assert "Title: Report" in result
        assert "Author: Alice" in result
        assert "Pretext: Here is the report" in result
        assert "Text: Some content" in result
        assert "Footer: Bot" in result

    def test_empty_attachment(self):
        assert attachment_to_text({}) == ""

    def test_replaces_parens(self):
        att = {"text": "Hello (world)"}
        result = attachment_to_text(att)
        assert "(" not in result
        assert "[world]" in result


class TestAttachmentsToTextUnit:
    def test_no_attachments(self):
        assert attachments_to_text("hello", []) == ""

    def test_with_prefix(self):
        result = attachments_to_text("msg", [{"text": "att"}])
        assert result.startswith(". ")

    def test_without_prefix(self):
        result = attachments_to_text("", [{"text": "att"}])
        assert not result.startswith(". ")


class TestBlocksToTextUnit:
    def test_empty_blocks(self):
        assert blocks_to_text([]) == ""

    def test_section_with_text(self):
        blocks = [{"type": "section", "text": {"type": "mrkdwn", "text": "Hello world"}}]
        result = blocks_to_text(blocks)
        assert "Hello world" in result

    def test_section_with_fields(self):
        blocks = [
            {
                "type": "section",
                "fields": [
                    {"type": "mrkdwn", "text": "*Status:* OK"},
                    {"type": "mrkdwn", "text": "*Trace:* abc-123"},
                ],
            }
        ]
        result = blocks_to_text(blocks)
        assert "*Status:* OK" in result
        assert "*Trace:* abc-123" in result

    def test_section_with_text_and_fields(self):
        blocks = [
            {
                "type": "section",
                "text": {"type": "mrkdwn", "text": "Summary"},
                "fields": [{"type": "mrkdwn", "text": "field1"}],
            }
        ]
        result = blocks_to_text(blocks)
        assert "Summary" in result
        assert "field1" in result

    def test_header_block(self):
        blocks = [{"type": "header", "text": {"type": "plain_text", "text": "Error Report"}}]
        result = blocks_to_text(blocks)
        assert "Error Report" in result

    def test_rich_text_section(self):
        blocks = [
            {
                "type": "rich_text",
                "elements": [
                    {
                        "type": "rich_text_section",
                        "elements": [
                            {"type": "text", "text": "Hello "},
                            {"type": "user", "user_id": "U123"},
                            {"type": "text", "text": " check this"},
                        ],
                    }
                ],
            }
        ]
        result = blocks_to_text(blocks)
        assert "Hello" in result
        assert "<@U123>" in result
        assert "check this" in result

    def test_rich_text_with_link(self):
        blocks = [
            {
                "type": "rich_text",
                "elements": [
                    {
                        "type": "rich_text_section",
                        "elements": [
                            {"type": "link", "url": "https://example.com", "text": "Example"},
                        ],
                    }
                ],
            }
        ]
        result = blocks_to_text(blocks)
        assert "Example" in result

    def test_rich_text_link_without_text(self):
        blocks = [
            {
                "type": "rich_text",
                "elements": [
                    {
                        "type": "rich_text_section",
                        "elements": [
                            {"type": "link", "url": "https://example.com"},
                        ],
                    }
                ],
            }
        ]
        result = blocks_to_text(blocks)
        assert "https://example.com" in result

    def test_rich_text_with_emoji(self):
        blocks = [
            {
                "type": "rich_text",
                "elements": [
                    {
                        "type": "rich_text_section",
                        "elements": [{"type": "emoji", "name": "rocket"}],
                    }
                ],
            }
        ]
        result = blocks_to_text(blocks)
        assert ":rocket:" in result

    def test_rich_text_list(self):
        blocks = [
            {
                "type": "rich_text",
                "elements": [
                    {
                        "type": "rich_text_list",
                        "elements": [
                            {
                                "type": "rich_text_section",
                                "elements": [{"type": "text", "text": "Item one"}],
                            },
                            {
                                "type": "rich_text_section",
                                "elements": [{"type": "text", "text": "Item two"}],
                            },
                        ],
                    }
                ],
            }
        ]
        result = blocks_to_text(blocks)
        assert "- Item one" in result
        assert "- Item two" in result

    def test_context_block(self):
        blocks = [
            {
                "type": "context",
                "elements": [
                    {"type": "mrkdwn", "text": "Last updated: today"},
                ],
            }
        ]
        result = blocks_to_text(blocks)
        assert "Last updated: today" in result

    def test_divider_ignored(self):
        blocks = [{"type": "divider"}]
        assert blocks_to_text(blocks) == ""

    def test_unknown_block_type_ignored(self):
        blocks = [{"type": "some_future_type", "data": "stuff"}]
        assert blocks_to_text(blocks) == ""

    def test_mixed_block_types(self):
        blocks = [
            {"type": "header", "text": {"type": "plain_text", "text": "Error Report"}},
            {"type": "divider"},
            {"type": "section", "text": {"type": "mrkdwn", "text": "trace_id: 1-abc-def"}},
            {
                "type": "context",
                "elements": [{"type": "mrkdwn", "text": "2 errors found"}],
            },
        ]
        result = blocks_to_text(blocks)
        assert "Error Report" in result
        assert "trace_id: 1-abc-def" in result
        assert "2 errors found" in result

    def test_result_has_prefix(self):
        blocks = [{"type": "section", "text": {"type": "mrkdwn", "text": "content"}}]
        result = blocks_to_text(blocks)
        assert result.startswith(". ")

    def test_table_block_raw_text(self):
        blocks = [
            {
                "type": "table",
                "rows": [
                    [
                        {"type": "raw_text", "text": "#"},
                        {"type": "raw_text", "text": "Service"},
                        {"type": "raw_text", "text": "Error Event"},
                        {"type": "raw_text", "text": "Count"},
                        {"type": "raw_text", "text": "Sample Trace"},
                    ],
                    [
                        {"type": "raw_text", "text": "1"},
                        {"type": "raw_text", "text": "analysis-agent"},
                        {"type": "raw_text", "text": "Code execution error"},
                        {"type": "raw_text", "text": "6"},
                        {"type": "raw_text", "text": "1-abc-def123"},
                    ],
                ],
            }
        ]
        result = blocks_to_text(blocks)
        assert "# | Service | Error Event | Count | Sample Trace" in result
        assert "1 | analysis-agent | Code execution error | 6 | 1-abc-def123" in result

    def test_table_block_with_rich_text_cells(self):
        blocks = [
            {
                "type": "table",
                "rows": [
                    [
                        {"type": "raw_text", "text": "Trace"},
                    ],
                    [
                        {
                            "type": "rich_text",
                            "elements": [
                                {
                                    "type": "rich_text_section",
                                    "elements": [
                                        {
                                            "type": "link",
                                            "url": "https://trace.example.com/1-abc",
                                            "text": "1-abc-def",
                                        }
                                    ],
                                }
                            ],
                        },
                    ],
                ],
            }
        ]
        result = blocks_to_text(blocks)
        assert "Trace" in result
        assert "1-abc-def" in result

    def test_table_block_empty_rows(self):
        blocks = [{"type": "table", "rows": []}]
        assert blocks_to_text(blocks) == ""
