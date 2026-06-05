"""Common utilities shared between async and sync browser modules."""

from __future__ import annotations

import functools
import os
import re
import subprocess
from pathlib import Path
from typing import Any

__all__ = [
    "DEFAULT_BROWSER_ARGS",
    "DEFAULT_BROWSER_VIEW_PORT",
    "DEFAULT_CUSTOM_USER_AGENT",
    "ECONOMIZING_BROWSER_ARGS",
    "LaunchArguments",
]


@functools.lru_cache(maxsize=1)
def _chromium_major_version() -> str:
    """Return the major version of the Playwright-bundled Chromium
    executable.
    """
    search_roots = [
        Path(os.environ.get("PATCHRIGHT_BROWSERS_PATH", Path.home() / ".cache" / "ms-patchright")),
        Path(os.environ.get("PLAYWRIGHT_BROWSERS_PATH", Path.home() / ".cache" / "ms-playwright")),
        Path("/ms-patchright"),
        Path("/ms-playwright"),
    ]
    for root in search_roots:
        for exe in sorted(root.glob("chromium-*/chrome-linux/chrome"), reverse=True):
            try:
                out = subprocess.run(  # noqa: S603
                    [str(exe), "--version"],
                    capture_output=True,
                    text=True,
                    check=False,
                    timeout=5,
                ).stdout
                m = re.search(r"(\d+)", out)
                if m:
                    return m.group(1)
            except (OSError, subprocess.TimeoutExpired):
                continue
    return "133"


def _build_user_agent(major: str) -> str:
    return (
        f"Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        f"AppleWebKit/537.36 (KHTML, like Gecko) Chrome/{major}.0.0.0 Safari/537.36"
    )


def _build_sec_ch_ua(major: str) -> str:
    return f'"Chromium";v="{major}", "Google Chrome";v="{major}", "Not_A Brand";v="99"'


# User-Agent を設定しないと WAON のページがレスポンスで HTML を返さない仕様になっていました
# User-Agent の設定方法は次を参考にしました:
# - Selenium User-Agent Guide: Changing and Rotating Headers
#   https://brightdata.com/blog/web-data/selenium-user-agent?kw=&cpn=13950045001&utm_matchtype=&utm_matchtype=&cq_src=google_ads&cq_cmp=13950045001&cq_term=&cq_plac=&cq_net=g&cq_plt=gp&utm_term=&utm_campaign=web_data-apac-search_generic-desktop&utm_source=adwords&utm_medium=ppc&utm_content=dataset-dsa&hsa_acc=1393175403&hsa_cam=13950045001&hsa_grp=133051793747&hsa_ad=622510825433&hsa_src=g&hsa_tgt=aud-1443847472521:dsa-1665041052623&hsa_kw=&hsa_mt=&hsa_net=adwords&hsa_ver=3&gad_source=1&gclid=CjwKCAiA5eC9BhAuEiwA3CKwQg952NCF0RakDla2KFWZ5W7OyspldKq9RUaE6IIw1XPtUclAbNegCBoCz9AQAvD_BwE
# インストール済み Chromium のバージョンから動的に生成します
_CHROMIUM_MAJOR = _chromium_major_version()
DEFAULT_CUSTOM_USER_AGENT = _build_user_agent(_CHROMIUM_MAJOR)
DEFAULT_EXTRA_HTTP_HEADERS = {
    # Sec-CH-UA を設定しないと WAON のページがレスポンスで HTML を返さない仕様になっていました
    "sec-ch-ua": _build_sec_ch_ua(_CHROMIUM_MAJOR),
    "sec-ch-ua-platform": '"Windows"',
    "sec-ch-ua-mobile": "?0",
}

DEFAULT_BROWSER_ARGS = [
    # To avoid detection as a headless browser from some websites
    "--disable-blink-features=AutomationControlled",
    # To print PDF without print dialog
    "--kiosk-printing",
    # To print PDF in headless mode without opening a new tab
    "--remote-debugging-port=9222",
]
# How to prevent crash due to out of memory:
# - herokuでselenium利用時にクラッシュする場合の解決方法 #Python - Qiita
#   https://qiita.com/kozasa/items/8a9d181e43fa0a85f6e5#%EF%BC%91-selenium%E3%81%AE%E5%BC%95%E6%95%B0%E3%81%AB%E7%9C%81%E3%83%A1%E3%83%A2%E3%83%AA%E5%8C%96%E3%81%99%E3%82%8B%E3%81%9F%E3%82%81%E3%81%AE%E5%BC%95%E6%95%B0%E3%82%92%E3%81%A4%E3%81%91%E3%82%8B
# - How to get headless Chrome running on AWS Lambda | by Marco Lüthy | Medium
#   https://adieuadieu.medium.com/running-headless-chrome-on-aws-lambda-fa82ad33a9eb
# Note: Playwright doesn't require the root user check that Selenium did
# Playwright can run as root without --no-sandbox issues
ECONOMIZING_BROWSER_ARGS = [
    "--disable-dev-shm-usage",
    "--disable-extensions",
    "--disable-gpu",
    # - ヘッドレスChrome(Chromium)がzombie processを生み出してしまう場合の対処法 #puppeteer - Qiita
    #   https://qiita.com/grainrigi/blob/3f13b949310b669d08bb
    "--no-zygote",
]
# How to prevent crash due to out of memory:
# - herokuでselenium利用時にクラッシュする場合の解決方法 #Python - Qiita
#   https://qiita.com/kozasa/items/8a9d181e43fa0a85f6e5#%EF%BC%91-selenium%E3%81%AE%E5%BC%95%E6%95%B0%E3%81%AB%E7%9C%81%E3%83%A1%E3%83%A2%E3%83%AA%E5%8C%96%E3%81%99%E3%82%8B%E3%81%9F%E3%82%81%E3%81%AE%E5%BC%95%E6%95%B0%E3%82%92%E3%81%A4%E3%81%91%E3%82%8B
DEFAULT_BROWSER_VIEW_PORT = {"width": 1280, "height": 900}


class LaunchArguments:
    """Arguments for launching the browser and creating a context."""

    def __init__(
        self,
        *,
        is_economizing: bool = False,
        storage_state: Path | None = None,
        record_video_dir: str | None = None,
    ) -> None:
        extra = ECONOMIZING_BROWSER_ARGS if is_economizing else []
        self.browser_args = DEFAULT_BROWSER_ARGS + extra
        self.context_options = self.build_browser_context_options(
            storage_state=storage_state,
            record_video_dir=record_video_dir,
        )

    @staticmethod
    def build_browser_context_options(
        *,
        storage_state: Path | None = None,
        record_video_dir: str | None = None,
    ) -> dict[str, Any]:
        """Build browser context options."""
        opts: dict[str, Any] = {
            "viewport": DEFAULT_BROWSER_VIEW_PORT,
            "record_video_size": DEFAULT_BROWSER_VIEW_PORT,
            "user_agent": DEFAULT_CUSTOM_USER_AGENT,
            "extra_http_headers": DEFAULT_EXTRA_HTTP_HEADERS,
            "accept_downloads": True,
        }
        if storage_state is not None:
            opts["storage_state"] = storage_state
        if record_video_dir is not None:
            opts["record_video_dir"] = record_video_dir
        return opts
