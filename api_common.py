"""Common utilities shared between async and sync browser modules."""

from __future__ import annotations

from typing import TYPE_CHECKING
from typing import Any

if TYPE_CHECKING:
    from pathlib import Path

__all__ = [
    "DEFAULT_BROWSER_ARGS",
    "DEFAULT_BROWSER_VIEW_PORT",
    "DEFAULT_CUSTOM_USER_AGENT",
    "ECONOMIZING_BROWSER_ARGS",
    "LaunchArguments",
]

# User-Agent を設定しないと WAON のページがレスポンスで HTML を返さない仕様になっていました
# User-Agent の設定方法は次を参考にしました:
# - Selenium User-Agent Guide: Changing and Rotating Headers
#   https://brightdata.com/blog/web-data/selenium-user-agent?kw=&cpn=13950045001&utm_matchtype=&utm_matchtype=&cq_src=google_ads&cq_cmp=13950045001&cq_term=&cq_plac=&cq_net=g&cq_plt=gp&utm_term=&utm_campaign=web_data-apac-search_generic-desktop&utm_source=adwords&utm_medium=ppc&utm_content=dataset-dsa&hsa_acc=1393175403&hsa_cam=13950045001&hsa_grp=133051793747&hsa_ad=622510825433&hsa_src=g&hsa_tgt=aud-1443847472521:dsa-1665041052623&hsa_kw=&hsa_mt=&hsa_net=adwords&hsa_ver=3&gad_source=1&gclid=CjwKCAiA5eC9BhAuEiwA3CKwQg952NCF0RakDla2KFWZ5W7OyspldKq9RUaE6IIw1XPtUclAbNegCBoCz9AQAvD_BwE
DEFAULT_CUSTOM_USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/133.0.0.0 Safari/537.36"
)
DEFAULT_EXTRA_HTTP_HEADERS = {
    # Sec-CH-UA を設定しないと WAON のページがレスポンスで HTML を返さない仕様になっていました
    "sec-ch-ua": '"Chromium";v="142", "Google Chrome";v="142", "Not_A Brand";v="99"'
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
DEFAULT_BROWSER_VIEW_PORT = {"width": 480, "height": 600}


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
