"""The module of web page."""

from logging import getLogger

from playwrightscraping.sync_api import ScrapingBrowser

__all__ = ["WebPage"]


# Reason: This is a base class. pylint: disable=too-few-public-methods
class WebPage:
    def __init__(self, browser: ScrapingBrowser) -> None:
        self.logger = getLogger(__name__)
        self.browser = browser
