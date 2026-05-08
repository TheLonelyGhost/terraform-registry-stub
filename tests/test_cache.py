import json
from unittest.mock import AsyncMock, patch

import pytest

from terraform_registry_stub.cache import cache_provider, cache_providers, resolve_platforms
from terraform_registry_stub.models import Manifest, Platform, Provider


@pytest.mark.asyncio
class TestCacheProvider:
    async def test_cache_provider_no_matches(self, tmp_cache_dir, sample_provider_versions):
        from rich.progress import Progress

        client = AsyncMock()
        client.get_provider_versions.return_value = sample_provider_versions

        provider = Provider(
            namespace="hashicorp",
            type="aws",
            version_constraints=[">=10.0.0"],
            platforms=[Platform(os="linux", arch="amd64")],
        )

        with Progress() as progress:
            result = await cache_provider(
                client=client,
                provider=provider,
                output_dir=tmp_cache_dir,
                download_packages=False,
                verify_signatures=False,
                force=False,
                progress=progress,
            )

        assert result["status"] == "no_matches"
        assert result["versions"] == 0

    async def test_cache_provider_success(
        self, tmp_cache_dir, sample_provider_versions, sample_package_metadata
    ):
        from rich.progress import Progress

        client = AsyncMock()
        client.get_provider_versions.return_value = sample_provider_versions
        client.get_provider_package.return_value = sample_package_metadata

        provider = Provider(
            namespace="hashicorp",
            type="aws",
            version_constraints=[">=5.0.0,<6.0.0"],
            platforms=[Platform(os="linux", arch="amd64")],
        )

        with Progress() as progress:
            result = await cache_provider(
                client=client,
                provider=provider,
                output_dir=tmp_cache_dir,
                download_packages=False,
                verify_signatures=False,
                force=False,
                progress=progress,
            )

        assert result["status"] == "success"
        assert result["versions"] >= 1
        assert result["packages"] >= 1

    async def test_cache_provider_creates_versions_file(
        self, tmp_cache_dir, sample_provider_versions, sample_package_metadata
    ):
        from rich.progress import Progress

        client = AsyncMock()
        client.get_provider_versions.return_value = sample_provider_versions
        client.get_provider_package.return_value = sample_package_metadata

        provider = Provider(
            namespace="hashicorp",
            type="aws",
            version_constraints=["5.0.0"],
            platforms=[Platform(os="linux", arch="amd64")],
        )

        with Progress() as progress:
            await cache_provider(
                client=client,
                provider=provider,
                output_dir=tmp_cache_dir,
                download_packages=False,
                verify_signatures=False,
                force=False,
                progress=progress,
            )

        versions_path = tmp_cache_dir / "providers" / "hashicorp" / "aws" / "versions.json"
        assert versions_path.exists()

        with open(versions_path) as f:
            data = json.load(f)
            assert data["id"] == "hashicorp/aws"

    async def test_cache_provider_creates_package_metadata(
        self, tmp_cache_dir, sample_provider_versions, sample_package_metadata
    ):
        from rich.progress import Progress

        client = AsyncMock()
        client.get_provider_versions.return_value = sample_provider_versions
        client.get_provider_package.return_value = sample_package_metadata

        provider = Provider(
            namespace="hashicorp",
            type="aws",
            version_constraints=["5.0.0"],
            platforms=[Platform(os="linux", arch="amd64")],
        )

        with Progress() as progress:
            await cache_provider(
                client=client,
                provider=provider,
                output_dir=tmp_cache_dir,
                download_packages=False,
                verify_signatures=False,
                force=False,
                progress=progress,
            )

        package_path = (
            tmp_cache_dir / "providers" / "hashicorp" / "aws" / "5.0.0" / "linux_amd64.json"
        )
        assert package_path.exists()

    async def test_cache_provider_with_download_packages(
        self, tmp_cache_dir, sample_provider_versions, sample_package_metadata
    ):
        from rich.progress import Progress

        client = AsyncMock()
        client.get_provider_versions.return_value = sample_provider_versions
        client.get_provider_package.return_value = sample_package_metadata
        client.download_file = AsyncMock()

        provider = Provider(
            namespace="hashicorp",
            type="aws",
            version_constraints=["5.0.0"],
            platforms=[Platform(os="linux", arch="amd64")],
        )

        with Progress() as progress:
            await cache_provider(
                client=client,
                provider=provider,
                output_dir=tmp_cache_dir,
                download_packages=True,
                verify_signatures=False,
                force=False,
                progress=progress,
            )

        assert client.download_file.call_count >= 1

    async def test_cache_provider_with_verify_signatures(
        self, tmp_cache_dir, sample_provider_versions, sample_package_metadata
    ):
        from rich.progress import Progress

        client = AsyncMock()
        client.get_provider_versions.return_value = sample_provider_versions
        client.get_provider_package.return_value = sample_package_metadata
        client.download_file = AsyncMock()

        provider = Provider(
            namespace="hashicorp",
            type="aws",
            version_constraints=["5.0.0"],
            platforms=[Platform(os="linux", arch="amd64")],
        )

        with Progress() as progress:
            await cache_provider(
                client=client,
                provider=provider,
                output_dir=tmp_cache_dir,
                download_packages=True,
                verify_signatures=True,
                force=False,
                progress=progress,
            )

        assert client.download_file.call_count == 3


class TestResolvePlatforms:
    @pytest.mark.asyncio
    async def test_explicit_platforms(self, sample_provider_versions):
        provider = Provider(
            namespace="hashicorp",
            type="aws",
            version_constraints=["5.0.0"],
            platforms=[Platform(os="linux", arch="amd64")],
        )

        platforms = await resolve_platforms(provider, sample_provider_versions, ["5.0.0"])

        assert len(platforms) == 1
        assert platforms[0].os == "linux"
        assert platforms[0].arch == "amd64"

    @pytest.mark.asyncio
    async def test_wildcard_platforms(self, sample_provider_versions):
        provider = Provider(
            namespace="hashicorp",
            type="aws",
            version_constraints=["5.0.0"],
            platforms=["*"],
        )

        platforms = await resolve_platforms(provider, sample_provider_versions, ["5.0.0"])

        assert len(platforms) >= 1
        assert all(isinstance(p, Platform) for p in platforms)


@pytest.mark.asyncio
class TestCacheProviders:
    async def test_cache_providers_creates_output_dir(self, tmp_path, sample_manifest_dict):
        output_dir = tmp_path / "new_cache"
        manifest = Manifest(**sample_manifest_dict)

        with patch("terraform_registry_stub.cache.AsyncRegistryClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_client.get_provider_versions.return_value = {
                "id": "hashicorp/aws",
                "versions": [{"version": "5.0.0", "platforms": [{"os": "linux", "arch": "amd64"}]}],
            }
            mock_client.get_provider_package.return_value = {
                "filename": "test.zip",
                "download_url": "https://example.com/test.zip",
                "shasums_url": "https://example.com/shasums",
                "shasums_signature_url": "https://example.com/sig",
            }
            mock_client_class.return_value = mock_client

            await cache_providers(manifest, output_dir)

            assert output_dir.exists()

    async def test_cache_providers_multiple_providers(self, tmp_path):
        manifest = Manifest(
            providers=[
                Provider(
                    namespace="hashicorp",
                    type="aws",
                    version_constraints=["5.0.0"],
                    platforms=[Platform(os="linux", arch="amd64")],
                ),
                Provider(
                    namespace="hashicorp",
                    type="random",
                    version_constraints=["latest"],
                    platforms=[Platform(os="linux", arch="amd64")],
                ),
            ]
        )

        with patch("terraform_registry_stub.cache.AsyncRegistryClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_client.get_provider_versions.return_value = {
                "id": "test/test",
                "versions": [{"version": "1.0.0", "platforms": [{"os": "linux", "arch": "amd64"}]}],
            }
            mock_client.get_provider_package.return_value = {
                "filename": "test.zip",
                "download_url": "https://example.com/test.zip",
                "shasums_url": "https://example.com/shasums",
                "shasums_signature_url": "https://example.com/sig",
            }
            mock_client_class.return_value = mock_client

            await cache_providers(manifest, tmp_path)

            assert mock_client.get_provider_versions.call_count == 2
