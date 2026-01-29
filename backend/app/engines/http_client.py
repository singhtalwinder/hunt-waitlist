"""Shared HTTP client factory for consistent HTTP behavior across engines.

This module provides a centralized way to create and configure httpx.AsyncClient
instances, ensuring consistent timeouts, headers, and settings across the codebase.

Usage:
    from app.engines.http_client import create_http_client, get_default_headers

    # For simple use cases with context manager
    async with create_http_client() as client:
        response = await client.get("https://example.com")

    # For services that manage their own lifecycle
    client = create_http_client()
    try:
        response = await client.get("https://example.com")
    finally:
        await client.aclose()
"""

from typing import Optional

import httpx

from app.config import get_settings

settings = get_settings()


def get_default_headers(
    user_agent: Optional[str] = None,
    accept: str = "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    json_accept: bool = False,
) -> dict[str, str]:
    """
    Get default headers for HTTP requests.
    
    Args:
        user_agent: Custom user agent string. Defaults to settings.crawl_user_agent.
        accept: Accept header value. Defaults to HTML/XML preference.
        json_accept: If True, sets Accept header for JSON responses.
        
    Returns:
        Dictionary of HTTP headers.
    """
    if json_accept:
        accept = "application/json, text/html"
    
    return {
        "User-Agent": user_agent or settings.crawl_user_agent,
        "Accept": accept,
        "Accept-Language": "en-US,en;q=0.5",
        "Accept-Encoding": "gzip, deflate",
        "Connection": "keep-alive",
    }


def create_http_client(
    timeout: Optional[float] = None,
    follow_redirects: bool = True,
    user_agent: Optional[str] = None,
    json_accept: bool = False,
    headers: Optional[dict[str, str]] = None,
) -> httpx.AsyncClient:
    """
    Create a configured httpx.AsyncClient with consistent defaults.
    
    This factory ensures all HTTP clients across the application use
    consistent timeouts, headers, and settings.
    
    Args:
        timeout: Request timeout in seconds. Defaults to settings.crawl_timeout_seconds.
        follow_redirects: Whether to follow HTTP redirects. Default True.
        user_agent: Custom user agent string. Defaults to settings.crawl_user_agent.
        json_accept: If True, sets Accept header for JSON responses.
        headers: Additional headers to merge with defaults.
        
    Returns:
        Configured httpx.AsyncClient instance.
        
    Example:
        async with create_http_client() as client:
            response = await client.get("https://example.com/api")
            
        # Or with custom settings
        client = create_http_client(timeout=15.0, json_accept=True)
    """
    default_timeout = timeout if timeout is not None else float(settings.crawl_timeout_seconds)
    default_headers = get_default_headers(
        user_agent=user_agent,
        json_accept=json_accept,
    )
    
    # Merge any additional headers
    if headers:
        default_headers.update(headers)
    
    return httpx.AsyncClient(
        timeout=default_timeout,
        follow_redirects=follow_redirects,
        headers=default_headers,
    )


class ManagedHttpClient:
    """
    A managed HTTP client that can be lazily initialized and reused.
    
    Useful for service classes that need a persistent client across
    multiple method calls.
    
    Example:
        class MyService:
            def __init__(self):
                self._http = ManagedHttpClient()
            
            async def fetch_data(self):
                client = await self._http.get_client()
                return await client.get("https://example.com")
            
            async def close(self):
                await self._http.close()
    """
    
    def __init__(
        self,
        timeout: Optional[float] = None,
        json_accept: bool = False,
        user_agent: Optional[str] = None,
    ):
        self._timeout = timeout
        self._json_accept = json_accept
        self._user_agent = user_agent
        self._client: Optional[httpx.AsyncClient] = None
    
    async def get_client(self) -> httpx.AsyncClient:
        """Get or create the HTTP client."""
        if self._client is None:
            self._client = create_http_client(
                timeout=self._timeout,
                json_accept=self._json_accept,
                user_agent=self._user_agent,
            )
        return self._client
    
    async def close(self) -> None:
        """Close the HTTP client if it exists."""
        if self._client:
            await self._client.aclose()
            self._client = None
