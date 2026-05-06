"""Cache configuration for Playwright libraries."""

from pathlib import Path


class PlaywrightScrapingCache:
    """Configurable cache paths for Playwright scraping."""

    def __init__(self, base: Path | None = None) -> None:
        if base is None:
            base = Path()
        self.base = base

    @property
    def directory_download(self) -> Path:
        """Return the path to the download cache directory."""
        return self.base / "downloads"

    def ensure_exists(self) -> None:
        """Create the download cache directory if it does not exist."""
        self.directory_download.mkdir(parents=True, exist_ok=True)
