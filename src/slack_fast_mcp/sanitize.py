from __future__ import annotations


def wrap_slack_content(text: str) -> str:
    if not text:
        return text
    return f"[SLACK_CONTENT]{text}[/SLACK_CONTENT]"
