"""Entry point: uv run python -m slack_fast_mcp"""


def main() -> None:
    from slack_fast_mcp.server import mcp

    mcp.run()


if __name__ == "__main__":
    main()
