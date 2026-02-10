# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

A Slack MCP (Model Context Protocol) server built with FastMCP that gives AI assistants tools to read, search, and interact with Slack workspaces. Python 3.13+, fully async. Package name: `slack_fast_mcp`.

## Common Commands

```bash
make build       # Install dependencies (uv sync --all-extras)
make test        # Run unit tests (uv run pytest tests/ -v -k "Unit")
make format      # Format code (uv run ruff format src/ tests/)
make lint        # Lint code (uv run ruff check src/ tests/)
```

Run a single test file or test:
```bash
uv run pytest tests/test_conversations_unit.py -v
uv run pytest tests/test_search_unit.py -v -k "test_search_with_date_range"
```

Run the server locally:
```bash
export SLACK_MCP_XOXP_TOKEN=xoxp-...
uv run python -m slack_fast_mcp
```

## Architecture

Uses Pattern B from the FastMCP conventions: module-level `mcp` instance with lifespan, thin `@mcp.tool()` wrappers in tool modules delegating to testable implementation functions.

```
server.py              ←  Module-level mcp = FastMCP(...) + lifespan (init SlackClient, Cache, Config)
__main__.py            ←  Entry point: imports mcp from server and calls mcp.run()
    ├── tools/         ←  8 tool modules with @mcp.tool() wrappers + implementation functions
    ├── resources/     ←  2 resources with @mcp.resource() wrappers (channels directory, users directory)
    ├── slack_client.py  ←  Thin async wrapper around Slack SDK's AsyncWebClient
    ├── cache.py         ←  Dual in-memory + disk-persistent cache with TTL and inverse name→ID mappings
    ├── config.py        ←  Environment variable–based configuration with channel allow/blocklist gating
    ├── types.py         ←  Pydantic models (Message, ChannelInfo, UserInfo, etc.)
    ├── text.py          ←  Timestamp conversion, link processing, text sanitization
    └── sanitize.py      ←  Wraps all Slack content in [SLACK_CONTENT]...[/SLACK_CONTENT] tags
```

### Key design patterns

- **Tool registration**: Each tool module imports `mcp` from `server.py` and registers `@mcp.tool()` wrappers that get context via `mcp.get_context()` and delegate to implementation functions. `server.py` imports all tool modules at the bottom to trigger registration.
- **Write operation gating**: Dangerous tools (messages, reactions) are disabled by default. Enabled via env vars (`SLACK_MCP_ADD_MESSAGE_TOOL`, `SLACK_MCP_REACTION_TOOL`) which support granular channel allow/blocklists.
- **Channel resolution**: Cache maintains forward (ID→name) and inverse (name→ID) mappings so tools accept both channel IDs (`C123`) and names (`#general`, `@alice`).
- **All responses are JSON strings**: Tools return `json.dumps()` output, not Python dicts.
- **Content wrapping**: All Slack-sourced content is wrapped in `[SLACK_CONTENT]...[/SLACK_CONTENT]` tags via `sanitize.py`.
- **Cursor-based pagination**: Paginated responses embed a cursor in the last item for the next page.

### Configuration (environment variables)

Authentication requires one of: `SLACK_MCP_XOXP_TOKEN` (user token, preferred — required for search), `SLACK_MCP_XOXB_TOKEN` (bot token), or both `SLACK_MCP_XOXC_TOKEN` + `SLACK_MCP_XOXD_TOKEN` (browser cookie auth, no app install needed). Priority: xoxp > xoxb > xoxc+xoxd. Tool gating vars accept `"true"` for blanket enable or comma-separated channel IDs for allowlists; prefix IDs with `!` for blocklists. Cannot mix allow and block in the same config value.

### Pre-commit hooks

The project uses pre-commit with ruff (format + import sorting) and `ty check` (type checking). Run type checking manually with `uv run ty check`.

### Testing conventions

- All tests are in `tests/` with `test_*_unit.py` naming
- `conftest.py` provides fixtures: `mock_client` (AsyncMock), `sample_users`, `sample_channels`, `populated_cache`, `default_config`, `write_enabled_config`
- Tests call implementation functions directly (not MCP wrappers), mocking `SlackClient` with `unittest.mock.AsyncMock`
- `asyncio_mode = "auto"` in pyproject.toml — no need for `@pytest.mark.asyncio` decorators
- Search tool (`conversations_search_messages`) requires a user token (`xoxp`); it won't work with bot tokens

### Adding a new tool

1. Create the async implementation function in `src/slack_fast_mcp/tools/<module>.py`
2. In the same file, add a `@mcp.tool()` wrapper that gets context and delegates to the implementation
3. Import the module in `server.py` to trigger registration
4. Add tests in `tests/test_<module>_unit.py`
5. If the tool is a write operation, gate it behind an env var in `config.py`
