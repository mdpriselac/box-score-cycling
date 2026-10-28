import cloudscraper
import os
import time
from typing import Optional, Dict
import random

from cycling_project.webscrape_tools.logging_config import get_logger

# Configure logger
logger = get_logger("scrape_client")


def _browser_backend_enabled() -> bool:
    """SCRAPER_USE_BROWSER=1/true/yes asked for the private browser backend."""
    return os.getenv("SCRAPER_USE_BROWSER", "").strip().lower() in ("1", "true", "yes")


class WebClient:
    def __init__(self, base_url: str):
        self.base_url = base_url.rstrip('/')

        # The browser-backed fetcher used for FirstCycling is not part of the public
        # copy. Bring your own data source, or your own fetcher behind this interface
        # (.text / .status_code / .raise_for_status()).
        self._browser = None
        if _browser_backend_enabled():
            raise RuntimeError(
                "SCRAPER_USE_BROWSER is set, but the browser backend is not included in "
                "this repository. Unset it, or supply your own fetcher."
            )
        self.client = self._build_scraper()
        logger.info(f"WebClient initialized with base URL: {base_url}")

        # Track request timing for rate limiting
        self.last_request_time = 0
        self.min_request_interval = 3  # Minimum seconds between requests

    @staticmethod
    def _build_scraper() -> 'cloudscraper.CloudScraper':
        return cloudscraper.create_scraper(
            browser={
                'browser': 'firefox',
                'platform': 'darwin',
                'desktop': True,
            }
        )

    def get(self, url: str, headers: Optional[Dict] = None, _retry_403: bool = True) -> 'cloudscraper.requests.Response':
        """Make a GET request with built-in rate limiting and error handling."""
        # Browser backend handles its own rate limiting + challenge waiting.
        if self._browser is not None:
            full_url = url if url.startswith('http') else f"{self.base_url}{url}"
            response = self._browser.fetch(full_url, headers=headers)
            response.raise_for_status()
            return response

        # Ensure minimum time between requests
        time_since_last = time.time() - self.last_request_time
        if time_since_last < self.min_request_interval:
            sleep_time = self.min_request_interval - time_since_last + random.uniform(0, 1)
            logger.debug(f"Rate limiting: sleeping for {sleep_time:.2f} seconds")
            time.sleep(sleep_time)

        # Clear cookies before each request. FirstCycling's Cloudflare layer
        # rejects reused cookies after the first response, so we force
        # cloudscraper to re-solve the challenge each time.
        self.client.cookies.clear()

        try:
            # Build full URL if relative
            full_url = url if url.startswith('http') else f"{self.base_url}{url}"

            logger.debug(f"Making GET request to {full_url}")
            response = self.client.get(full_url, headers=headers)
            response.raise_for_status()

            # Update last request time
            self.last_request_time = time.time()

            logger.debug(f"Request successful: {response.status_code}")
            return response

        except Exception as e:
            if hasattr(e, 'response') and e.response is not None:
                status = e.response.status_code
                if status == 429:  # Too Many Requests
                    retry_after = int(e.response.headers.get('Retry-After', 60))
                    logger.warning(f"Rate limited (429): sleeping for {retry_after} seconds")
                    time.sleep(retry_after)
                    return self.get(url, headers)  # Retry the request
                if status == 403 and _retry_403:
                    # Cloudflare blocked us — rebuild the scraper from scratch
                    # (new TLS fingerprint + fresh challenge) and retry once.
                    logger.warning("403 Forbidden: rebuilding scraper and retrying once")
                    try:
                        self.client.close()
                    except Exception:
                        pass
                    self.client = self._build_scraper()
                    self.last_request_time = time.time()  # account for retry delay
                    time.sleep(self.min_request_interval + random.uniform(0, 1))
                    return self.get(url, headers, _retry_403=False)
                logger.error(f"HTTP error: {status} - {str(e)}")
            else:
                logger.error(f"Request error: {str(e)}")
            raise

    def close(self):
        """Close the client session.

        The browser backend is a shared, process-wide instance — closing a
        single WebClient must NOT tear it down (the scrapers close a client
        per race). It is closed once at process exit via atexit. Only the
        per-instance cloudscraper session is closed here.
        """
        logger.debug("Closing WebClient session")
        if self.client is not None:
            self.client.close()


# Example usage
if __name__ == "__main__":
    client = WebClient("https://example.com")
    try:
        response = client.get("/path")
        print(response.text)
    finally:
        client.close()