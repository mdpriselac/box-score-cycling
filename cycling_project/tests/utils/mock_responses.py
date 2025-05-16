"""
Utilities for creating mock HTTP responses for testing.
"""
import json
import os
from pathlib import Path
from typing import Dict, Any, Optional, Union

import httpx


class MockResponse:
    """
    Mock HTTP response for testing web scraping tools.
    Can be loaded from HTML files or created programmatically.
    """
    def __init__(
        self, 
        text: str = "", 
        status_code: int = 200, 
        headers: Optional[Dict[str, str]] = None,
        url: str = "https://example.com"
    ):
        self.text = text
        self.status_code = status_code
        self.headers = headers or {}
        self.url = url
        
    @classmethod
    def from_html_file(cls, filepath: Union[str, Path], status_code: int = 200):
        """
        Create a MockResponse from an HTML file.
        
        Args:
            filepath: Path to the HTML file
            status_code: HTTP status code for the response
            
        Returns:
            MockResponse instance
        """
        with open(filepath, 'r', encoding='utf-8') as f:
            content = f.read()
        
        return cls(
            text=content,
            status_code=status_code,
            headers={"Content-Type": "text/html; charset=utf-8"}
        )
    
    @classmethod
    def from_json_file(cls, filepath: Union[str, Path], status_code: int = 200):
        """
        Create a MockResponse from a JSON file.
        
        Args:
            filepath: Path to the JSON file
            status_code: HTTP status code for the response
            
        Returns:
            MockResponse instance with JSON content
        """
        with open(filepath, 'r', encoding='utf-8') as f:
            data = json.load(f)
            
        content = json.dumps(data)
        return cls(
            text=content,
            status_code=status_code,
            headers={"Content-Type": "application/json; charset=utf-8"}
        )
        
    def raise_for_status(self):
        """
        Mimic httpx's raise_for_status method.
        Raises HTTPStatusError for 4xx and 5xx status codes.
        """
        if 400 <= self.status_code < 600:
            raise httpx.HTTPStatusError(
                f"{self.status_code} Error",
                request=None,
                response=self
            )


class MockWebClient:
    """
    Mock web client for testing.
    Allows preprogrammed responses or loading from HTML files.
    """
    def __init__(self, base_url: str = "https://example.com"):
        self.base_url = base_url
        self.responses = {}
        self.requests = []
        
    def add_response(self, url: str, response: MockResponse):
        """Add a preprogrammed response for a specific URL."""
        self.responses[url] = response
        
    def add_html_response(self, url: str, filepath: Union[str, Path], status_code: int = 200):
        """Add an HTML file response for a URL."""
        self.responses[url] = MockResponse.from_html_file(filepath, status_code)
        
    def get(self, url: str, headers: Optional[Dict] = None) -> MockResponse:
        """
        Mock GET request. Returns a preprogrammed response or 404.
        
        Args:
            url: URL to request
            headers: Optional request headers
            
        Returns:
            MockResponse instance
        """
        self.requests.append({"url": url, "headers": headers})
        
        if url in self.responses:
            return self.responses[url]
        
        # Return 404 if URL not found
        return MockResponse(
            text="<html><body><h1>404 Not Found</h1></body></html>",
            status_code=404,
            url=url
        )
        
    def close(self):
        """Mock close method."""
        pass