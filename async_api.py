"""The module about asynchronous browser."""

from __future__ import annotations

import contextlib
from logging import getLogger
from typing import TYPE_CHECKING
from typing import Self

from playwright.async_api import async_playwright

from playwrightscraping.api_common import build_browser_args
from playwrightscraping.api_common import build_browser_context_options

if TYPE_CHECKING:
    from pathlib import Path
    from types import TracebackType

    from playwright.async_api import Browser
    from playwright.async_api import BrowserContext
    from playwright.async_api import Page
    from playwright.async_api import Playwright

__all__ = [
    "ResponseChecker",
    "ScrapingBrowser",
]


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
    def __init__(self, key: str) -> None:
        self.key = key

    async def log_response(self, response: object) -> None:
        logger = getLogger(__name__)
        url = response.url  # type: ignore[attr-defined]
        if self.key in url and not url.endswith((".js", ".css", ".png", ".svg", ".woff2")):
            with contextlib.suppress(Exception):
                body = await response.json()  # type: ignore[attr-defined]
                logger.info("[network] %s %s", response.status, url)  # type: ignore[attr-defined]
                logger.info("[network] body: %s", body)


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
        self.logger = getLogger(__name__)
        self.is_economizing = is_economizing
        self._storage_state = storage_state
        self._response_checker = response_checker
        self._take_screenshot = take_screenshot
        self._playwright: Playwright | None = None
        self._browser: Browser | None = None
        self._context: BrowserContext | None = None
        self._page: Page | None = None

    async def __aenter__(self) -> Self:
        self._playwright = await async_playwright().start()
        args = build_browser_args(is_economizing=self.is_economizing)
        self._browser = await self._playwright.chromium.launch(args=args)
        self._context = await self._browser.new_context(
            **build_browser_context_options(storage_state=self._storage_state)
        )
        self._page = await self._context.new_page()
        await self._setup_webauthn()
        await self._context.add_init_script(_WEBDRIVER_HIDE_SCRIPT)
        self._page.on("console", lambda msg: self.logger.info("[browser:%s] %s", msg.type, msg.text))
        if self._response_checker:
            self._page.on("response", self._response_checker.log_response)
        return self

    async def _setup_webauthn(self) -> None:
        cdp = await self._context.new_cdp_session(self._page)  # type: ignore[union-attr, arg-type]
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

    async def __aexit__(
        self,
        _exc_type: type[BaseException] | None,
        _exc_value: BaseException | None,
        _traceback: TracebackType | None,
    ) -> None:
        if self._page and self._take_screenshot:
            await self._page.screenshot(path="final_state.png")
        await self.close_if_needed()

    async def close_if_needed(self) -> None:
        """Closes the browser if it's still open.

        Useful for cleanup in case of unexpected errors.
        """
        if self._context:
            await self._context.close()
        if self._browser:
            await self._browser.close()
        if self._playwright:
            await self._playwright.stop()

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

    async def storage_state(self, path: Path) -> None:
        if self._context is None:
            msg = "Browser context is not initialized. Use async context manager."
            raise RuntimeError(msg)
        await self._context.storage_state(path=path)
