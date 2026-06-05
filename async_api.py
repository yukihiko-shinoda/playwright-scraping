"""The module about asynchronous browser."""

from __future__ import annotations

import asyncio
import contextlib
import os
import subprocess
import sys
from logging import getLogger
from pathlib import Path as _Path
from typing import TYPE_CHECKING
from typing import Protocol
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

_JS_DIR = _Path(__file__).parent / "js"


__all__ = [
    "FirefoxScrapingBrowser",
    "ResponseChecker",
    "ScrapingBrowser",
    "ScrapingBrowserProtocol",
]


class ScrapingBrowserProtocol(Protocol):
    @property
    def context(self) -> BrowserContext: ...

    @property
    def page(self) -> Page: ...

    async def wait_for(self, selector: str, *, timeout: float | None = None) -> Locator: ...

    async def storage_state(self, path: Path) -> None: ...


class _PlaywrightHandles:
    def __init__(self, *, is_economizing: bool = False, storage_state: Path | None = None) -> None:
        self.args = LaunchArguments(is_economizing=is_economizing, storage_state=storage_state)
        self._playwright: Playwright | None = None
        self._browser: Browser | None = None
        self._context: BrowserContext | None = None
        self._page: Page | None = None

    async def __aenter__(self) -> Self:
        """Start Playwright, launch browser, and create context and first
        page.
        """
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


_WEBDRIVER_HIDE_SCRIPT = (_JS_DIR / "navigator-webdriver-hide.js").read_text()
_AKAMAI_FORM_DELAY_INIT = (_JS_DIR / "akamai-form-submit-delay-init.js").read_text()


def _system_firefox_executable() -> str | None:
    """Return the installed Firefox binary path on macOS, or None to use
    Playwright's bundled build.

    Akamai Bot Manager fingerprints the TLS ClientHello.  Playwright's
    bundled Firefox has a non-standard fingerprint that Akamai blocks
    for authenticated paths.  The release Firefox from mozilla.org has
    an allowlisted fingerprint.
    """
    if sys.platform == "darwin":
        path = "/Applications/Firefox.app/Contents/MacOS/firefox"
        if os.path.exists(path):
            return path
    return None


class _FirefoxHandles:
    def __init__(self, *, storage_state: Path | None = None) -> None:
        self._storage_state = storage_state
        self._xvfb: asyncio.subprocess.Process | None = None
        self._playwright: Playwright | None = None
        self._browser: Browser | None = None
        self._context: BrowserContext | None = None
        self._page: Page | None = None

    async def __aenter__(self) -> Self:
        if sys.platform != "darwin":
            self._xvfb = await asyncio.create_subprocess_exec(
                "/usr/bin/Xvfb",
                ":99",
                "-screen",
                "0",
                "1440x900x24",
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
            os.environ["DISPLAY"] = ":99"
        self._playwright = await async_playwright().start()
        self._browser = await self._playwright.firefox.launch(
            # Use Playwright's bundled Firefox rather than system Firefox.
            # System Firefox crashes on launch (GPU Helper fails to connect to
            # com.apple.hiservices-xpcservice) after being manually opened and closed.
            # Playwright's bundled Firefox is built for this use case and avoids the issue.
            # On macOS, it uses the same NSS/TLS stack so the TLS fingerprint still passes
            # Akamai's allowlist check (the requirement is macOS host, not system Firefox).
            headless=False,  # headless=True is also blocked by Akamai even with system Firefox
            firefox_user_prefs={
                # This preference has no effect — Playwright overrides it at runtime
                # regardless.  The actual fix is the prototype-level patch in
                # akamai-form-submit-delay-init.js.  Kept as belt-and-suspenders intent.
                "dom.webdriver.enabled": False,
            },
        )
        context_options: dict[str, object] = {"accept_downloads": True}
        if self._storage_state is not None:
            context_options["storage_state"] = self._storage_state
        if sys.platform != "darwin":
            # Spoof macOS Firefox profile so Akamai's JS sensor does not detect Linux signals.
            # Derive the Firefox major version from the running browser to stay in sync with Playwright.
            ff_major = self._browser.version.split(".")[0]
            context_options["user_agent"] = (
                f"Mozilla/5.0 (Macintosh; Intel Mac OS X 10.15; rv:{ff_major}.0) Gecko/20100101 Firefox/{ff_major}.0"
            )
            # Viewport matches the Xvfb display (1440x900) and the JS-patched screen.width/height.
            # Playwright's default 1280px viewport creates a detectable innerWidth ≠ screen.width gap.
            context_options["viewport"] = {"width": 1440, "height": 900}
            # locale sets navigator.language; without it Firefox returns undefined on Linux.
            context_options["locale"] = "en-US"
        # Reason: Playwright's type stubs are incomplete for new_context options; ignore type errors.
        self._context = await self._browser.new_context(**context_options)  # type: ignore[arg-type]
        # Hide navigator.webdriver before any page loads so Akamai's beacon JS
        # does not flag this session as automated.  Also patches form submit to
        # delay navigation until Akamai's sensor POST completes (see js/ for details).
        await self._context.add_init_script(_AKAMAI_FORM_DELAY_INIT)
        self._page = await self._context.new_page()
        return self

    async def __aexit__(
        self,
        _exc_type: type[BaseException] | None,
        _exc_value: BaseException | None,
        _traceback: TracebackType | None,
    ) -> None:
        if self._context:
            await self._context.close()
        if self._browser:
            await self._browser.close()
        if self._playwright:
            await self._playwright.stop()
        await self._stop_xvfb()

    async def _stop_xvfb(self) -> None:
        if self._xvfb:
            if self._xvfb.returncode is None:
                self._xvfb.terminate()
            await self._xvfb.wait()

    async def screenshot(self, path: str) -> None:
        if self._page:
            await self._page.screenshot(path=path)

    async def save_storage_state(self, path: Path) -> None:
        if self._context is None:
            msg = "Browser context is not initialized. Use async context manager."
            raise RuntimeError(msg)
        await self._context.storage_state(path=path)

    @property
    def context(self) -> BrowserContext:
        if self._context is None:
            msg = "Browser context is not initialized. Use async context manager."
            raise RuntimeError(msg)
        return self._context

    @property
    def page(self) -> Page:
        if self._page is None:
            msg = "Browser page is not initialized. Use async context manager."
            raise RuntimeError(msg)
        return self._page


class FirefoxScrapingBrowser:
    """Async context manager for a headless Firefox browser.

    Use instead of ScrapingBrowser for sites that block Chromium via
    HTTP/2 fingerprinting.
    """

    def __init__(
        self,
        *,
        storage_state: Path | None = None,
        take_screenshot: bool = False,
    ) -> None:
        self._take_screenshot = take_screenshot
        self._handles = _FirefoxHandles(storage_state=storage_state)
        self.logger = getLogger(__name__)

    async def __aenter__(self) -> Self:
        await self._handles.__aenter__()
        return self

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
        """Enable logging of WebAuthn virtual authenticator usage and hide
        webdriver property for anti-bot evasion.
        """
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
