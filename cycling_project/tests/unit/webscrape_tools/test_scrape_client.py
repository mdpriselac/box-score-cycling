"""
Unit tests for the scrape_client module.
"""
import pytest
import httpx
from unittest.mock import patch, MagicMock

from cycling_project.webscrape_tools.scrape_client import WebClient


def make_transport(*responses):
    """Return a requests-like transport without opening a network socket."""
    transport = MagicMock()
    if responses:
        transport.get.side_effect = responses
    return transport


def test_webclient_initialization():
    """Test WebClient initialization with default settings."""
    transport = make_transport()
    with patch.object(WebClient, '_build_scraper', return_value=transport):
        client = WebClient("https://example.com/")

    assert client.base_url == "https://example.com"
    assert client.client is transport
    assert client._browser is None
    assert client.min_request_interval == 3

    client.close()
    transport.close.assert_called_once_with()


def test_webclient_rate_limiting():
    """Test that WebClient enforces rate limiting between requests."""
    response = MagicMock()
    transport = make_transport(response, response)
    with patch.object(WebClient, '_build_scraper', return_value=transport), \
         patch('cycling_project.webscrape_tools.scrape_client.time.time',
               side_effect=[100, 100, 101, 101]), \
         patch('cycling_project.webscrape_tools.scrape_client.time.sleep') as mock_sleep, \
         patch('cycling_project.webscrape_tools.scrape_client.random.uniform', return_value=0):
        client = WebClient("https://example.com")
        client.get("/test1")
        client.get("/test2")

    mock_sleep.assert_called_once_with(2)
    assert transport.get.call_args_list[0].args[0] == "https://example.com/test1"
    assert transport.get.call_args_list[1].args[0] == "https://example.com/test2"
    client.close()


def test_webclient_retry_on_429():
    """Test that WebClient retries after receiving a 429 Too Many Requests."""
    error_response = MagicMock(status_code=429, headers={"Retry-After": "10"})
    mock_response_429 = MagicMock()
    mock_response_429.raise_for_status.side_effect = httpx.HTTPStatusError(
        "429 Too Many Requests", request=MagicMock(), response=error_response
    )
    mock_response_ok = MagicMock()
    transport = make_transport(mock_response_429, mock_response_ok)

    with patch.object(WebClient, '_build_scraper', return_value=transport), \
         patch('cycling_project.webscrape_tools.scrape_client.time.sleep') as mock_sleep:
        client = WebClient("https://example.com")
        response = client.get("/test")

        mock_sleep.assert_called_once_with(10)
        assert transport.get.call_count == 2
        assert response is mock_response_ok

    client.close()


def test_webclient_error_handling():
    """Test that WebClient properly handles other HTTP errors."""
    error = httpx.HTTPStatusError(
        "404 Not Found", request=MagicMock(), response=MagicMock(status_code=404)
    )
    transport = make_transport(error)
    with patch.object(WebClient, '_build_scraper', return_value=transport):
        client = WebClient("https://example.com")
        with pytest.raises(httpx.HTTPStatusError):
            client.get("/nonexistent")

    client.close()


def test_webclient_custom_headers():
    """Test that WebClient forwards custom headers to its transport."""
    mock_response = MagicMock()
    transport = make_transport(mock_response)
    with patch.object(WebClient, '_build_scraper', return_value=transport):
        client = WebClient("https://example.com")
        custom_headers = {"X-Custom-Header": "TestValue"}
        client.get("/test", headers=custom_headers)

    transport.get.assert_called_once_with(
        "https://example.com/test", headers=custom_headers
    )
    client.close()
