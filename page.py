"""The module of web page."""

from __future__ import annotations

from logging import getLogger
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from playwrightscraping.async_api import ScrapingBrowserProtocol

__all__ = ["WebPage"]


# Reason: This is a base class. pylint: disable=too-few-public-methods
class WebPage:
    def __init__(self, browser: ScrapingBrowserProtocol) -> None:
        self.logger = getLogger(__name__)
        self.browser = browser
