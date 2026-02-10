# slack-fast-mcp

A Slack MCP server built with [FastMCP](https://github.com/jlowin/fastmcp) that gives AI assistants tools to read, search, and interact with Slack workspaces. Python 3.13+, fully async.

## Features

**Read tools** (always available):
- `conversations_history` — Get messages from a channel or DM
- `conversations_replies` — Get a thread of messages
- `conversations_search_messages` — Search messages with filters (requires user token)
- `channels_list` — List channels
- `users_search` — Search users by name, email, or display name
- `attachment_get_data` — Download file attachments (up to 5MB)

**Write tools** (disabled by default, opt-in via env vars):
- `conversations_add_message` — Post a message to a channel or DM
- `reactions_add` / `reactions_remove` — Add or remove emoji reactions

**Resources:**
- `slack://{workspace}/users` — User directory
- `slack://{workspace}/channels` — Channel directory

## Authentication

Three authentication methods are supported, in priority order:

### 1. User token (recommended)

Requires a Slack app with user token scopes. Supports all features including message search.

```bash
export SLACK_MCP_XOXP_TOKEN=xoxp-...
```

### 2. Bot token

Requires a Slack app with bot token scopes. Cannot search messages.

```bash
export SLACK_MCP_XOXB_TOKEN=xoxb-...
```

### 3. Browser cookie auth (no app install required)

Uses your existing Slack browser session. No Slack app installation or workspace admin approval needed — useful when your workspace restricts app installs.

```bash
export SLACK_MCP_XOXC_TOKEN=xoxc-...
export SLACK_MCP_XOXD_TOKEN=xoxd-...
```

Both values must be set together. To extract them:

1. Open your Slack workspace in a browser and log in
2. Open DevTools (F12)
3. **xoxc token** — paste this in the browser console:
   ```javascript
   JSON.parse(localStorage.localConfig_v2).teams[document.location.pathname.match(/^\/client\/([A-Z0-9]+)/)[1]].token
   ```
4. **xoxd token** — go to Application > Cookies > `https://app.slack.com`, copy the value of the cookie named `d`

**Caveats:**
- Tokens are tied to your browser session and will expire when you log out or Slack rotates sessions. You'll need to re-extract them periodically.
- All API calls appear as your user account, not a bot.
- This uses standard Slack API endpoints with session cookies — it does not use undocumented internal APIs.

## Installation

```bash
uv sync --all-extras
```

## Usage

```bash
export SLACK_MCP_XOXP_TOKEN=xoxp-...  # or xoxb/xoxc+xoxd (see above)
uv run python -m slack_fast_mcp
```

### Claude Desktop / Claude Code

Add to your MCP config:

```json
{
  "mcpServers": {
    "slack": {
      "command": "uv",
      "args": ["run", "--project", "/path/to/slack-fast-mcp", "python", "-m", "slack_fast_mcp"],
      "env": {
        "SLACK_MCP_XOXP_TOKEN": "xoxp-..."
      }
    }
  }
}
```

## Configuration

All configuration is via environment variables.

### Token (required — one of)

| Variable | Description |
|---|---|
| `SLACK_MCP_XOXP_TOKEN` | User OAuth token (priority 1) |
| `SLACK_MCP_XOXB_TOKEN` | Bot OAuth token (priority 2) |
| `SLACK_MCP_XOXC_TOKEN` | Browser session token (priority 3, requires `XOXD` too) |
| `SLACK_MCP_XOXD_TOKEN` | Browser `d` cookie value (priority 3, requires `XOXC` too) |

### Write tool gating (optional)

Write tools are disabled by default. Enable them with these env vars. Each accepts:
- `"true"` or `"1"` — enable for all channels
- Comma-separated channel IDs — allowlist (e.g. `C001,C002`)
- `!`-prefixed channel IDs — blocklist (e.g. `!C003,!C004`)

| Variable | Controls |
|---|---|
| `SLACK_MCP_ADD_MESSAGE_TOOL` | `conversations_add_message` |
| `SLACK_MCP_REACTION_TOOL` | `reactions_add` / `reactions_remove` |
| `SLACK_MCP_ATTACHMENT_TOOL` | `attachment_get_data` |

### Other options

| Variable | Default | Description |
|---|---|---|
| `SLACK_MCP_LOG_LEVEL` | `info` | Log level (`debug`, `info`, `warning`, `error`) |
| `SLACK_MCP_CACHE_TTL` | `3600` | Cache TTL in seconds, or duration string (`1h`, `30m`, `3600s`) |
| `SLACK_MCP_ADD_MESSAGE_MARK` | `false` | Mark channel as read when sending a message |
| `SLACK_MCP_ADD_MESSAGE_UNFURLING` | `""` | Control link unfurling in sent messages |
| `SLACK_MCP_USERS_CACHE` | auto | Path to persistent users cache file |
| `SLACK_MCP_CHANNELS_CACHE` | auto | Path to persistent channels cache file |

## Development

```bash
make build       # Install dependencies
make test        # Run unit tests
make format      # Format code (ruff)
make lint        # Lint code (ruff)
```
