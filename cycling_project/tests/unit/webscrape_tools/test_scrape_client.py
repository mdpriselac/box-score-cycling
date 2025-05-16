"""
Unit tests for the scrape_client module.
"""
import pytest
import time
import httpx
from unittest.mock import patch, MagicMock

from cycling_project.webscrape_tools.scrape_client import WebClient


def test_webclient_initialization():
    """Test WebClient initialization with default settings."""
    client = WebClient("https://example.com")
    
    assert client.client.base_url == httpx.URL("https://example.com")
    assert client.min_request_interval == 3
    assert "User-Agent" in client.default_headers
    
    # Clean up
    client.close()


def test_webclient_rate_limiting():
    """Test that WebClient enforces rate limiting between requests."""
    with patch('httpx.Client.get') as mock_get:
        # Configure mock to return a successful response
        mock_response = MagicMock()
        mock_response.raise_for_status.return_value = None
        mock_get.return_value = mock_response
        
        client = WebClient("https://example.com")
        
        # Make first request
        start_time = time.time()
        client.get("/test1")
        
        # Make second request immediately
        client.get("/test2")
        end_time = time.time()
        
        # The second request should be delayed by at least min_request_interval
        assert end_time - start_time >= client.min_request_interval
        
        # Clean up
        client.close()


def test_webclient_retry_on_429():
    """Test that WebClient retries after receiving a 429 Too Many Requests."""
    with patch('httpx.Client.get') as mock_get, \
         patch('time.sleep') as mock_sleep:  # Mock sleep to speed up test
        
        # First call raises 429, second succeeds
        mock_response_429 = MagicMock()
        mock_response_429.raise_for_status.side_effect = httpx.HTTPStatusError(
            "429 Too Many Requests", 
            request=MagicMock(), 
            response=MagicMock(status_code=429, headers={"Retry-After": "10"})
        )
        
        mock_response_ok = MagicMock()
        mock_response_ok.raise_for_status.return_value = None
        
        mock_get.side_effect = [mock_response_429, mock_response_ok]
        
        client = WebClient("https://example.com")
        response = client.get("/test")
        
        # Verify sleep was called with retry-after value
        mock_sleep.assert_called_once_with(10)
        
        # Verify get was called twice
        assert mock_get.call_count == 2
        
        # Clean up
        client.close()


def test_webclient_error_handling():
    """Test that WebClient properly handles other HTTP errors."""
    with patch('httpx.Client.get') as mock_get:
        # Configure mock to raise an HTTP error
        mock_get.side_effect = httpx.HTTPStatusError(
            "404 Not Found", 
            request=MagicMock(), 
            response=MagicMock(status_code=404)
        )
        
        client = WebClient("https://example.com")
        
        # The error should be re-raised
        with pytest.raises(httpx.HTTPStatusError):
            client.get("/nonexistent")
            
        # Clean up
        client.close()


def test_webclient_custom_headers():
    """Test that WebClient properly merges custom headers."""
    with patch('httpx.Client.get') as mock_get:
        # Configure mock to return a successful response
        mock_response = MagicMock()
        mock_response.raise_for_status.return_value = None
        mock_get.return_value = mock_response
        
        client = WebClient("https://example.com")
        custom_headers = {"X-Custom-Header": "TestValue"}
        
        client.get("/test", headers=custom_headers)
        
        # Extract the headers argument from the call
        called_kwargs = mock_get.call_args[1]
        
        # Verify custom header was included
        assert "X-Custom-Header" in called_kwargs["headers"]
        assert called_kwargs["headers"]["X-Custom-Header"] == "TestValue"
        
        # Verify default headers were also included
        assert "User-Agent" in called_kwargs["headers"]
        
        # Clean up
        client.close()