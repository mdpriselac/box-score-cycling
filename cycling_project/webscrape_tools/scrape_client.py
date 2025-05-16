import httpx
import time
from typing import Optional, Dict
import random

from cycling_project.webscrape_tools.logging_config import get_logger

# Configure logger
logger = get_logger("scrape_client")

class WebClient:
    def __init__(self, base_url: str):
        # Common headers that make the request look more like a regular browser
        self.default_headers = {
            'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10.15; rv:134.0) Gecko/20100101 Firefox/134.0',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.5',
            'Accept-Encoding': 'gzip, deflate, br',
            'DNT': '1',
            'Connection': 'keep-alive',
            'Upgrade-Insecure-Requests': '1',
        }
        
        # Configure client with reasonable timeouts and limits
        self.client = httpx.Client(
            base_url=base_url,
            timeout=30.0,
            limits=httpx.Limits(max_keepalive_connections=5, max_connections=10),
            headers=self.default_headers,
            follow_redirects=True
        )
        
        # Track request timing for rate limiting
        self.last_request_time = 0
        self.min_request_interval = 3  # Minimum seconds between requests
        
        logger.info(f"WebClient initialized with base URL: {base_url}")
        
    def get(self, url: str, headers: Optional[Dict] = None) -> httpx.Response:
        """Make a GET request with built-in rate limiting and error handling."""
        # Ensure minimum time between requests
        time_since_last = time.time() - self.last_request_time
        if time_since_last < self.min_request_interval:
            sleep_time = self.min_request_interval - time_since_last + random.uniform(0, 1)
            logger.debug(f"Rate limiting: sleeping for {sleep_time:.2f} seconds")
            time.sleep(sleep_time)
            
        try:
            # Merge default headers with any custom headers
            request_headers = self.default_headers.copy()
            if headers:
                request_headers.update(headers)
                
            logger.debug(f"Making GET request to {url}")
            response = self.client.get(url, headers=request_headers)
            response.raise_for_status()
            
            # Update last request time
            self.last_request_time = time.time()
            
            logger.debug(f"Request successful: {response.status_code}")
            return response
            
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 429:  # Too Many Requests
                retry_after = int(e.response.headers.get('Retry-After', 60))
                logger.warning(f"Rate limited (429): sleeping for {retry_after} seconds")
                time.sleep(retry_after)
                return self.get(url, headers)  # Retry the request
            
            logger.error(f"HTTP error: {e.response.status_code} - {str(e)}")
            raise
            
        except httpx.RequestError as e:
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