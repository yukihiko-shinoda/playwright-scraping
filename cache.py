"""Cache configuration for Playwright libraries."""

from pathlib import Path


class PlaywrightScrapingCache:
    """Configurable cache paths for Playwright scraping."""

    def __init__(self, base: Path | None = None) -> None:
        if base is None:
            base = Path()
        self.base = base
        self.directory_download = base / "downloads"
