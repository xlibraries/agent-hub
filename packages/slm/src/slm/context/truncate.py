from __future__ import annotations


def truncate_text(text: str, max_chars: int, *, label: str = "section") -> str:
    """Keep the start of text within a character budget."""
    if max_chars <= 0:
        return f"(omitted: {label})"
    if len(text) <= max_chars:
        return text
    omitted = len(text) - max_chars
    return text[: max_chars - 48] + f"\n\n…({label} truncated, {omitted} chars omitted)"
