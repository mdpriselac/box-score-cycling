import cloudscraper
import time
from typing import Optional, Dict
import random

from cycling_project.webscrape_tools.logging_config import get_logger

# Configure logger
logger = get_logger("scrape_client")

class WebClient:
    def __init__(self, base_url: str):
        self.base_url = base_url.rstrip('/')

        # Create cloudscraper session to handle Cloudflare protection
        self.client = cloudscraper.create_scraper(
            browser={
                'browser': 'firefox',
                'platform': 'darwin',
                'desktop': True
            }
        )

        # Track request timing for rate limiting
        self.last_request_time = 0
        self.min_request_interval = 3  # Minimum seconds between requests

        logger.info(f"WebClient initialized with base URL: {base_url}")

    def get(self, url: str, headers: Optional[Dict] = None) -> 'cloudscraper.requests.Response':
        """Make a GET request with built-in rate limiting and error handling."""
        # Ensure minimum time between requests
        time_since_last = time.time() - self.last_request_time
        if time_since_last < self.min_request_interval:
            sleep_time = self.min_request_interval - time_since_last + random.uniform(0, 1)
            logger.debug(f"Rate limiting: sleeping for {sleep_time:.2f} seconds")
            time.sleep(sleep_time)

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
                if e.response.status_code == 429:  # Too Many Requests
                    retry_after = int(e.response.headers.get('Retry-After', 60))
                    logger.warning(f"Rate limited (429): sleeping for {retry_after} seconds")
                    time.sleep(retry_after)
                    return self.get(url, headers)  # Retry the request
                logger.error(f"HTTP error: {e.response.status_code} - {str(e)}")
            else:
                logger.error(f"Request error: {str(e)}")
            raise

    def close(self):
        """Close the client session."""
        logger.debug("Closing WebClient session")
        self.client.close()


# Example usage
if __name__ == "__main__":
    client = WebClient("https://example.com")
    try:
        response = client.get("/path")
        print(response.text)
    finally:
        client.close()