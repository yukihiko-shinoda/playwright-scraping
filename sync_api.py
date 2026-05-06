"""The module about synchronous browser."""

from __future__ import annotations

import time
from typing import TYPE_CHECKING
from typing import Any
from typing import Self

from playwright.sync_api import sync_playwright

from playwrightscraping.api_common import LaunchArguments
from playwrightscraping.cache import PlaywrightScrapingCache

if TYPE_CHECKING:
    from pathlib import Path
    from types import TracebackType

    from playwright.sync_api import Browser
    from playwright.sync_api import BrowserContext
    from playwright.sync_api import Locator
    from playwright.sync_api import Page
    from playwright.sync_api import Playwright

__all__ = ["ScrapingBrowser"]


class _PlaywrightHandles:
    def __init__(self, *, is_economizing: bool = False, storage_state: Path | None = None) -> None:
        self.args = LaunchArguments(is_economizing=is_economizing, storage_state=storage_state)
        self.playwright: Playwright | None = None
        self.browser: Browser | None = None
        self._context: BrowserContext | None = None
        self._page: Page | None = None

    def __enter__(self) -> Self:
        """Start Playwright, launch browser, and create context and first page."""
        self.playwright = sync_playwright().start()
        self.browser = self.playwright.chromium.launch(args=self.args.browser_args)
        self._context = self.browser.new_context(**self.args.context_options)
        self._page = self._context.new_page()
        return self

    def __exit__(
        self,
        _exc_type: type[BaseException] | None,
        _exc_value: BaseException | None,
        _traceback: TracebackType | None,
    ) -> None:
        """Close context, browser, and stop Playwright if open."""
        if self._context:
            self._context.close()
        if self.browser:
            self.browser.close()
        if self.playwright:
            self.playwright.stop()

    @property
    def context(self) -> BrowserContext:
        """Get the current browser context."""
        if self._context is None:
            msg = "Browser context is not initialized. Use context manager."
            raise RuntimeError(msg)
        return self._context

    @property
    def page(self) -> Page:
        """Get the current page."""
        if self._page is None:
            msg = "Browser page is not initialized. Use context manager."
            raise RuntimeError(msg)
        return self._page


class Downloading:
    """Polls a download directory until all files have finished downloading."""

    INTERVAL = 0.5

    def __init__(self, directory_download: Path, timeout: float, number_of_files: int | None) -> None:
        self.directory_download = directory_download
        self.seconds = 0.0
        self.timeout = timeout
        self.number_of_files = number_of_files

    def wait(self) -> None:
        while self.seconds < self.timeout:
            self._wait()

    def _wait(self) -> None:
        files = list(self.directory_download.iterdir())
        # Check if we have the expected number of files
        if self.number_of_files and len(files) != self.number_of_files:
            time.sleep(self.INTERVAL)
            self.seconds += self.INTERVAL
            return
        # Check for incomplete downloads
        has_incomplete = any(str(f).endswith(".crdownload") for f in files)
        if not has_incomplete:
            return
        time.sleep(self.INTERVAL)
        self.seconds += self.INTERVAL


class ScrapingBrowser:
    """The browser."""

    def __init__(
        self,
        *,
        is_economizing: bool = False,
        storage_state: Path | None = None,
        download_dir: Path | None = None,
    ) -> None:
        self.directory_download = download_dir or PlaywrightScrapingCache().directory_download
        self._handles = _PlaywrightHandles(is_economizing=is_economizing, storage_state=storage_state)

    def __enter__(self) -> Self:
        """Start Playwright browser."""
        self._handles.__enter__()
        return self

    def __exit__(
        self,
        _exc_type: type[BaseException] | None,
        _exc_value: BaseException | None,
        _traceback: TracebackType | None,
    ) -> None:
        """Clean up Playwright resources."""
        self._handles.__exit__(_exc_type, _exc_value, _traceback)

    @property
    def context(self) -> BrowserContext:
        """Get the current browser context."""
        return self._handles.context

    @property
    def page(self) -> Page:
        """Get the current page."""
        return self._handles.page

    def wait_for(self, selector: str, *, timeout: float | None = None) -> Locator:
        """Wait for an element to be present.

        Args:
            selector: CSS selector, XPath, or other Playwright selector
            timeout: Optional timeout in seconds (default: 10s)

        Returns:
            Locator for the element
        """
        locator = self.page.locator(selector)
        if timeout is not None:
            locator = locator.first
            locator.wait_for(state="attached", timeout=timeout * 1000)
        else:
            locator = locator.first
            locator.wait_for(state="attached")
        return locator

    def scroll_and_click(self, selector: str) -> None:
        """Scroll to element and click it.

        Args:
            selector: CSS selector, XPath, or other Playwright selector
        """
        locator = self.page.locator(selector).first
        locator.scroll_into_view_if_needed()
        locator.click()

    def save_as_pdf(self, path: Path, *, options: dict[str, Any] | None = None) -> None:
        """Save current page as PDF.

        Args:
            path: Relative path within DIRECTORY_DOWNLOAD
            options: Optional PDF generation options
        """
        options = options or {}
        pdf_bytes = self.page.pdf(**options)
        output_path = self.directory_download / path
        output_path.write_bytes(pdf_bytes)

    def wait_for_download(self, timeout: int, number_of_files: int | None = None) -> None:
        """Wait for downloads to finish with a specified timeout.

        Note: This is a compatibility method. With Playwright, prefer using
        page.expect_download() context manager for better control.

        Args:
            timeout: How many seconds to wait until timing out.
            number_of_files: If provided, also wait for the expected number of files.
        """
        Downloading(self.directory_download, timeout, number_of_files).wait()

    def wait_for_closing_tab(self, expected_number_of_tabs: int, timeout: int) -> None:
        """Wait for closing tab.

        Args:
            expected_number_of_tabs: Expected number of pages/tabs
            timeout: Timeout in seconds
        """
        seconds = 0
        while len(self.context.pages) > expected_number_of_tabs:
            time.sleep(0.5)
            seconds += 1
            if seconds == timeout:
                # Close the current page
                self.page.close()
            if seconds > timeout:
                msg = "Timeout waiting for closing tab."
                raise TimeoutError(msg)
