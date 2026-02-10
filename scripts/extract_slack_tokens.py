#!/usr/bin/env -S python3 -u
"""Extract Slack xoxc/xoxd tokens from a browser session.

Uses Playwright with a persistent browser profile so you only need to
log in once. Subsequent runs reuse the existing session.

Usage:
    uv run --with playwright scripts/extract_slack_tokens.py [workspace_url]

First run will require:
    uv run --with playwright python -m playwright install chromium
"""

import asyncio
import sys
from pathlib import Path

DEFAULT_URL = "https://app.slack.com"


def log(msg: str) -> None:
    """Print to stderr so output is never buffered."""
    print(msg, file=sys.stderr, flush=True)


async def extract_slack_tokens(workspace_url: str) -> None:
    from playwright.async_api import async_playwright  # type: ignore

    profile_dir = str(Path(__file__).parent / ".slack-browser-profile")

    log("Launching browser...")

    async with async_playwright() as p:
        browser = await p.chromium.launch_persistent_context(
            user_data_dir=profile_dir,
            headless=False,
        )
        log("Browser launched.")
        page = browser.pages[0] if browser.pages else await browser.new_page()

        log(f"Navigating to {workspace_url} ...")
        await page.goto(workspace_url, wait_until="commit")
        log("Log in if the browser prompts.")
        log("Polling for tokens... Press Ctrl+C to abort.\n")

        # Poll localStorage until the xoxc token appears.
        # Slack stores it at localConfig_v2.teams[TEAM_ID].token.
        # Try the URL path first (/client/TXXXXX/), fall back to first team.
        xoxc = None
        for i in range(300):  # up to ~5 minutes
            try:
                xoxc = await page.evaluate("""
                    () => {
                        try {
                            const config = JSON.parse(localStorage.localConfig_v2);
                            const urlMatch = document.location.pathname
                                .match(/^\\/client\\/([A-Z0-9]+)/);
                            const teamId = urlMatch
                                ? urlMatch[1]
                                : Object.keys(config.teams)[0];
                            return config.teams[teamId].token;
                        } catch {
                            return null;
                        }
                    }
                """)
            except Exception:
                pass  # page navigating, context destroyed, etc.
            if xoxc:
                log("Found xoxc token!")
                break
            if i > 0 and i % 10 == 0:
                log(f"  still waiting... ({i}s)")
            await asyncio.sleep(1)

        # Extract xoxd from cookies
        cookies = await browser.cookies()
        xoxd = next((c["value"] for c in cookies if c["name"] == "d"), None)

        if not xoxc or not xoxd:
            await browser.close()
            log("\nFailed to extract tokens.")
            if not xoxc:
                log("  - xoxc: not found in localStorage")
            if not xoxd:
                log("  - xoxd: not found in cookies")
            log("\nMake sure you're fully logged in and the page has loaded.")
            sys.exit(1)

        auth_file = Path.home() / ".slack_xoxcd_auth"
        content = (
            f'export SLACK_MCP_XOXC_TOKEN="{xoxc}"\n'
            f'export SLACK_MCP_XOXD_TOKEN="{xoxd}"\n'
        )
        auth_file.write_text(content)
        log(f"Tokens written to {auth_file}")
        log("Run: source ~/.slack_xoxcd_auth")

        # Keep the browser alive — Slack invalidates xoxc/xoxd tokens when
        # the session ends. Press Ctrl+C to stop.
        log("\nKeeping browser open to maintain session. Press Ctrl+C to stop.")
        try:
            while True:
                await asyncio.sleep(3600)
        except asyncio.CancelledError:
            pass


if __name__ == "__main__":
    url = sys.argv[1] if len(sys.argv) > 1 else DEFAULT_URL
    asyncio.run(extract_slack_tokens(url))
