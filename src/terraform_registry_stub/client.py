"""HTTP client for interacting with Terraform registry."""

from pathlib import Path
from typing import Any

import httpx


class AsyncRegistryClient:
    """Async client for concurrent provider downloads from Terraform registry."""

    def __init__(self, base_url: str = "https://registry.terraform.io", timeout: float = 30.0):
        """
        Initialize the registry client.

        Args:
            base_url: Base URL of the registry (e.g., https://registry.terraform.io)
            timeout: Request timeout in seconds
        """
        self.base_url = base_url.rstrip("/")
        self.timeout = httpx.Timeout(timeout, connect=10.0)
        self.limits = httpx.Limits(max_keepalive_connections=5, max_connections=10)

    def _get_base_api_url(self) -> str:
        """Get the base API URL for provider endpoints."""
        return f"{self.base_url}/v1/providers"

    async def get_provider_versions(self, namespace: str, type_: str) -> dict[str, Any]:
        """
        Fetch available versions for a provider.

        Args:
            namespace: Provider namespace (e.g., "hashicorp")
            type_: Provider type (e.g., "aws")

        Returns:
            Dictionary containing versions information
        """
        url = f"{self._get_base_api_url()}/{namespace}/{type_}/versions"

        async with httpx.AsyncClient(timeout=self.timeout, limits=self.limits) as client:
            response = await client.get(url)
            response.raise_for_status()
            return response.json()

    async def get_provider_package(
        self, namespace: str, type_: str, version: str, os: str, arch: str
    ) -> dict[str, Any]:
        """
        Fetch package metadata for a specific provider version/platform.

        Args:
            namespace: Provider namespace
            type_: Provider type
            version: Provider version
            os: Operating system
            arch: Architecture

        Returns:
            Dictionary containing package metadata
        """
        url = f"{self._get_base_api_url()}/{namespace}/{type_}/{version}/download/{os}/{arch}"

        async with httpx.AsyncClient(
            timeout=self.timeout, limits=self.limits, follow_redirects=True
        ) as client:
            response = await client.get(url)
            response.raise_for_status()
            return response.json()

    async def download_file(self, url: str, output_path: Path) -> None:
        """
        Download a file (provider zip, checksums, signatures).

        Args:
            url: URL to download from
            output_path: Path to save the downloaded file
        """
        async with (
            httpx.AsyncClient(timeout=self.timeout) as client,
            client.stream("GET", url) as response,
        ):
            response.raise_for_status()
            output_path.parent.mkdir(parents=True, exist_ok=True)
            with open(output_path, "wb") as f:
                async for chunk in response.aiter_bytes(chunk_size=8192):
                    f.write(chunk)
