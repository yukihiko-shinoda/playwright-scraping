"""The module about asynchronous browser."""

from __future__ import annotations

import contextlib
from logging import getLogger
from typing import TYPE_CHECKING
from typing import Self

from playwright.async_api import async_playwright

from playwrightscraping.api_common import LaunchArguments

if TYPE_CHECKING:
    from collections.abc import Awaitable
    from collections.abc import Callable
    from pathlib import Path
    from types import TracebackType

    from playwright.async_api import Browser
    from playwright.async_api import BrowserContext
    from playwright.async_api import ConsoleMessage
    from playwright.async_api import Locator
    from playwright.async_api import Page
    from playwright.async_api import Playwright
    from playwright.async_api import Response


__all__ = [
    "ResponseChecker",
    "ScrapingBrowser",
]


class _PlaywrightHandles:
    def __init__(self, *, is_economizing: bool = False, storage_state: Path | None = None) -> None:
        self.args = LaunchArguments(is_economizing=is_economizing, storage_state=storage_state)
        self._playwright: Playwright | None = None
        self._browser: Browser | None = None
        self._context: BrowserContext | None = None
        self._page: Page | None = None

    async def __aenter__(self) -> Self:
        """Start Playwright, launch browser, and create context and first page."""
        self._playwright = await async_playwright().start()
        self._browser = await self._playwright.chromium.launch(args=self.args.browser_args)
        self._context = await self._browser.new_context(**self.args.context_options)
        self._page = await self._context.new_page()
        await self.enable_virtual_authenticator()
        return self

    async def __aexit__(
        self,
        _exc_type: type[BaseException] | None,
        _exc_value: BaseException | None,
        _traceback: TracebackType | None,
    ) -> None:
        """Close context, browser, and stop Playwright if open."""
        if self._context:
            await self._context.close()
        if self._browser:
            await self._browser.close()
        if self._playwright:
            await self._playwright.stop()

    async def enable_virtual_authenticator(self) -> None:
        """Enable a virtual authenticator for WebAuthn testing."""
        cdp = await self.context.new_cdp_session(self.page)
        await cdp.send("WebAuthn.enable", {"enableUI": True})
        await cdp.send(
            "WebAuthn.addVirtualAuthenticator",
            {
                "options": {
                    "protocol": "ctap2",
                    "transport": "internal",
                    "hasResidentKey": True,
                    "hasUserVerification": True,
                    "isUserVerified": True,
                    "automaticPresenceSimulation": True,
                },
            },
        )

    async def add_init_script(self, script: str) -> None:
        """Add a JavaScript init script to every new page in the context."""
        await self._context.add_init_script(script)  # type: ignore[union-attr]

    async def screenshot(self, path: str) -> None:
        """Save a screenshot of the current page to the given path."""
        if self._page:
            await self._page.screenshot(path=path)

    def on_console(self, handler: Callable[[ConsoleMessage], Awaitable[None] | None]) -> None:
        """Register a console event handler on the current page."""
        self._page.on("console", handler)  # type: ignore[union-attr]

    def on_response(self, handler: Callable[[Response], Awaitable[None] | None]) -> None:
        """Register a response event handler on the current page."""
        self._page.on("response", handler)  # type: ignore[union-attr]

    async def save_storage_state(self, path: Path) -> None:
        """Persist the browser context storage state to a file."""
        if self._context is None:
            msg = "Browser context is not initialized. Use async context manager."
            raise RuntimeError(msg)
        await self._context.storage_state(path=path)

    @property
    def context(self) -> BrowserContext:
        """Return the context, raising RuntimeError if not initialized."""
        if self._context is None:
            msg = "Browser context is not initialized. Use async context manager."
            raise RuntimeError(msg)
        return self._context

    @property
    def page(self) -> Page:
        """Return the page, raising RuntimeError if not initialized."""
        if self._page is None:
            msg = "Browser page is not initialized. Use async context manager."
            raise RuntimeError(msg)
        return self._page


# Purpose of this JavaScript snippet: To hide the webdriver property and log WebAuthn virtual authenticator usage for debugging.
_WEBDRIVER_HIDE_SCRIPT = """
    Object.defineProperty(navigator, 'webdriver', {get: () => undefined});
    if (typeof PublicKeyCredential !== 'undefined') {
        const _orig = navigator.credentials.create.bind(navigator.credentials);
        navigator.credentials.create = async function(opts) {
            console.log('[PASSKEY] create called, rp:', opts?.publicKey?.rp?.id);
            try {
                const r = await _orig(opts);
                console.log('[PASSKEY] create OK, id prefix:', r?.id?.substring(0, 12));
                return r;
            } catch (e) {
                console.log('[PASSKEY] create ERROR:', e.name, ':', e.message);
                throw e;
            }
        };
    }
"""


class ResponseChecker:
    """Logs network responses whose URL contains a configured key fragment."""

    def __init__(self, key: str) -> None:
        self.logger = getLogger(__name__)
        self.key = key

    async def log_response(self, response: Response) -> None:
        """Log the JSON body of matching non-static responses."""
        url = response.url
        if self.key in url and not url.endswith((".js", ".css", ".png", ".svg", ".woff2")):
            with contextlib.suppress(Exception):
                body = await response.json()
                self.logger.info("[network] %s %s", response.status, url)
                self.logger.info("[network] body: %s", body)


class ScrapingBrowser:
    """Async context manager for a headless Chromium browser."""

    def __init__(
        self,
        *,
        is_economizing: bool = False,
        storage_state: Path | None = None,
        response_checker: ResponseChecker | None = None,
        take_screenshot: bool = False,
    ) -> None:
        self._response_checker = response_checker
        self._take_screenshot = take_screenshot
        self._handles = _PlaywrightHandles(is_economizing=is_economizing, storage_state=storage_state)
        self.logger = getLogger(__name__)

    async def __aenter__(self) -> Self:
        await self._handles.__aenter__()
        await self.enable_log_virtual_authenticator()
        return self

    async def enable_log_virtual_authenticator(self) -> None:
        """Enable logging of WebAuthn virtual authenticator usage and hide webdriver property for anti-bot evasion."""
        await self._handles.add_init_script(_WEBDRIVER_HIDE_SCRIPT)
        self._handles.on_console(lambda msg: self.logger.info("[browser:%s] %s", msg.type, msg.text))
        if self._response_checker:
            self._handles.on_response(self._response_checker.log_response)

    async def __aexit__(
        self,
        _exc_type: type[BaseException] | None,
        _exc_value: BaseException | None,
        _traceback: TracebackType | None,
    ) -> None:
        if self._take_screenshot:
            await self._handles.screenshot(path="final_state.png")
        await self._handles.__aexit__(_exc_type, _exc_value, _traceback)

    @property
    def context(self) -> BrowserContext:
        return self._handles.context

    @property
    def page(self) -> Page:
        return self._handles.page

    async def storage_state(self, path: Path) -> None:
        await self._handles.save_storage_state(path)

    async def wait_for(self, selector: str, *, timeout: float | None = None) -> Locator:
        """Wait for an element to be present and return its locator."""
        locator = self.page.locator(selector).first
        if timeout is not None:
            await locator.wait_for(state="attached", timeout=timeout * 1000)
        else:
            await locator.wait_for(state="attached")
        return locator
