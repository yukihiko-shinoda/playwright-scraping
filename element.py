"""The module about element."""

from playwright.sync_api import Locator

__all__ = ["get_text"]


def get_text(locator: Locator) -> str:
    """Gets Playwright locator text.

    Playwright's text_content() returns all text including hidden elements,
    while inner_text() returns only visible text. We prefer inner_text()
    but fall back to text_content() if needed.

    Args:
        locator: Playwright locator

    Returns:
        Text of the element
    """
    # First try inner_text() which is closer to what users see
    inner_text = locator.inner_text()
    if inner_text:
        return inner_text

    # Fall back to text_content() which includes hidden text
    text_content = locator.text_content()
    if text_content:
        return text_content

    return ""
