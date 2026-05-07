import json
import shutil
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
import yaml
from fastapi.testclient import TestClient

from terraform_registry_stub.cache import cache_providers
from terraform_registry_stub.cli import load_manifest
from terraform_registry_stub.serve import init_app


@pytest.fixture
def example_manifest_path():
    return Path(__file__).parent.parent / "examples" / "manifest.yaml"


@pytest.fixture
def example_manifest(example_manifest_path):
    return load_manifest(example_manifest_path)


@pytest.fixture
def e2e_cache_dir(tmp_path):
    cache_dir = tmp_path / "e2e_cache"
    cache_dir.mkdir()
    return cache_dir


class TestManifestParsing:
    def test_load_example_manifest(self, example_manifest_path):
        manifest = load_manifest(example_manifest_path)
        assert manifest.registry == "registry.terraform.io"
        assert len(manifest.providers) == 5
        assert manifest.cache_options is not None
        assert manifest.cache_options.download_packages is True
        assert manifest.cache_options.verify_signatures is True

    def test_aws_provider_config(self, example_manifest):
        aws_provider = next(p for p in example_manifest.providers if p.type_ == "aws")
        assert aws_provider.namespace == "hashicorp"
        assert aws_provider.version_constraints == [">=5.0.0,<5.5.0"]
        assert len(aws_provider.platforms) == 3
        assert aws_provider.max_versions == 5
        assert aws_provider.include_prerelease is False

    def test_random_provider_config(self, example_manifest):
        random_provider = next(p for p in example_manifest.providers if p.type_ == "random")
        assert random_provider.namespace == "hashicorp"
        assert random_provider.version_constraints == ["latest"]
        assert random_provider.platforms == ["*"]

    def test_google_provider_config(self, example_manifest):
        google_provider = next(p for p in example_manifest.providers if p.type_ == "google")
        assert google_provider.namespace == "hashicorp"
        assert google_provider.version_constraints == [">=5.10.0,<5.11.0"]
        assert len(google_provider.platforms) == 1

    def test_ansible_provider_config(self, example_manifest):
        ansible_provider = next(p for p in example_manifest.providers if p.type_ == "aap")
        assert ansible_provider.namespace == "ansible"
        assert ansible_provider.version_constraints == ["latest"]
        assert len(ansible_provider.platforms) == 4

    def test_null_provider_config(self, example_manifest):
        null_provider = next(p for p in example_manifest.providers if p.type_ == "null")
        assert null_provider.namespace == "hashicorp"
        assert null_provider.version_constraints == ["*"]
        assert null_provider.max_versions == 20


@pytest.mark.asyncio
class TestCacheWorkflow:
    async def test_cache_providers_with_mocked_registry(self, example_manifest, e2e_cache_dir):
        mock_client = AsyncMock()
        
        mock_client.get_provider_versions.return_value = {
            "id": "hashicorp/aws",
            "versions": [
                {"version": "5.4.0", "platforms": [{"os": "linux", "arch": "amd64"}]},
                {"version": "5.3.0", "platforms": [{"os": "linux", "arch": "amd64"}]},
                {"version": "5.2.0", "platforms": [{"os": "linux", "arch": "amd64"}]},
                {"version": "5.1.0", "platforms": [{"os": "linux", "arch": "amd64"}]},
                {"version": "5.0.0", "platforms": [{"os": "linux", "arch": "amd64"}]},
            ],
        }
        
        mock_client.get_provider_package.return_value = {
            "protocols": ["5.0"],
            "os": "linux",
            "arch": "amd64",
            "filename": "terraform-provider-aws_5.0.0_linux_amd64.zip",
            "download_url": "https://releases.hashicorp.com/terraform-provider-aws/5.0.0/terraform-provider-aws_5.0.0_linux_amd64.zip",
            "shasums_url": "https://releases.hashicorp.com/terraform-provider-aws/5.0.0/terraform-provider-aws_5.0.0_SHA256SUMS",
            "shasums_signature_url": "https://releases.hashicorp.com/terraform-provider-aws/5.0.0/terraform-provider-aws_5.0.0_SHA256SUMS.sig",
            "shasum": "abc123",
            "signing_keys": {"gpg_public_keys": []},
        }
        
        mock_client.download_file = AsyncMock()

        with patch("terraform_registry_stub.cache.AsyncRegistryClient", return_value=mock_client):
            await cache_providers(
                manifest=example_manifest,
                output_dir=e2e_cache_dir,
                parallel=2,
                force=False,
            )

        assert mock_client.get_provider_versions.called
        assert (e2e_cache_dir / "providers").exists()

    async def test_cache_creates_directory_structure(self, e2e_cache_dir):
        mock_versions = {
            "id": "hashicorp/random",
            "versions": [{"version": "3.5.0", "platforms": [{"os": "linux", "arch": "amd64"}]}],
        }
        
        mock_package = {
            "filename": "terraform-provider-random_3.5.0_linux_amd64.zip",
            "download_url": "https://example.com/random.zip",
            "shasums_url": "https://example.com/shasums",
            "shasums_signature_url": "https://example.com/sig",
        }

        mock_client = AsyncMock()
        mock_client.get_provider_versions.return_value = mock_versions
        mock_client.get_provider_package.return_value = mock_package
        mock_client.download_file = AsyncMock()

        from terraform_registry_stub.models import Manifest, Platform, Provider

        manifest = Manifest(
            providers=[
                Provider(
                    namespace="hashicorp",
                    type="random",
                    version_constraints=["latest"],
                    platforms=[Platform(os="linux", arch="amd64")],
                )
            ]
        )

        with patch("terraform_registry_stub.cache.AsyncRegistryClient", return_value=mock_client):
            await cache_providers(manifest, e2e_cache_dir)

        versions_file = e2e_cache_dir / "providers" / "hashicorp" / "random" / "versions.json"
        assert versions_file.exists()

        package_file = e2e_cache_dir / "providers" / "hashicorp" / "random" / "3.5.0" / "linux_amd64.json"
        assert package_file.exists()


class TestServeWorkflow:
    def test_serve_with_cached_data(self, tmp_path):
        cache_dir = tmp_path / "cache"
        cache_dir.mkdir()
        
        provider_dir = cache_dir / "providers" / "hashicorp" / "aws"
        provider_dir.mkdir(parents=True)
        
        versions_data = {
            "id": "hashicorp/aws",
            "versions": [
                {"version": "5.0.0", "platforms": [{"os": "linux", "arch": "amd64"}]},
            ],
        }
        (provider_dir / "versions.json").write_text(json.dumps(versions_data))
        
        version_dir = provider_dir / "5.0.0"
        version_dir.mkdir()
        
        package_data = {
            "protocols": ["5.0"],
            "os": "linux",
            "arch": "amd64",
            "filename": "terraform-provider-aws_5.0.0_linux_amd64.zip",
            "download_url": "https://releases.hashicorp.com/file.zip",
            "shasums_url": "https://releases.hashicorp.com/shasums",
            "shasums_signature_url": "https://releases.hashicorp.com/sig",
        }
        (version_dir / "linux_amd64.json").write_text(json.dumps(package_data))

        app = init_app(cache_dir)
        client = TestClient(app)

        response = client.get("/.well-known/terraform.json")
        assert response.status_code == 200

        response = client.get("/v1/providers/hashicorp/aws/versions")
        assert response.status_code == 200
        assert response.json()["id"] == "hashicorp/aws"

        response = client.get("/v1/providers/hashicorp/aws/5.0.0/download/linux/amd64")
        assert response.status_code == 200
        assert "filename" in response.json()


class TestEndToEndIntegration:
    @pytest.mark.asyncio
    async def test_full_workflow_cache_then_serve(self, tmp_path):
        cache_dir = tmp_path / "full_workflow_cache"
        cache_dir.mkdir()

        mock_versions = {
            "id": "hashicorp/null",
            "versions": [
                {"version": "3.2.0", "platforms": [{"os": "linux", "arch": "amd64"}]},
                {"version": "3.1.0", "platforms": [{"os": "linux", "arch": "amd64"}]},
            ],
        }
        
        mock_package = {
            "protocols": ["5.0"],
            "os": "linux",
            "arch": "amd64",
            "filename": "terraform-provider-null_3.2.0_linux_amd64.zip",
            "download_url": "https://releases.hashicorp.com/terraform-provider-null/3.2.0/terraform-provider-null_3.2.0_linux_amd64.zip",
            "shasums_url": "https://releases.hashicorp.com/terraform-provider-null/3.2.0/terraform-provider-null_3.2.0_SHA256SUMS",
            "shasums_signature_url": "https://releases.hashicorp.com/terraform-provider-null/3.2.0/terraform-provider-null_3.2.0_SHA256SUMS.sig",
            "shasum": "def456",
        }

        mock_client = AsyncMock()
        mock_client.get_provider_versions.return_value = mock_versions
        mock_client.get_provider_package.return_value = mock_package
        mock_client.download_file = AsyncMock()

        from terraform_registry_stub.models import Manifest, Platform, Provider

        manifest = Manifest(
            providers=[
                Provider(
                    namespace="hashicorp",
                    type="null",
                    version_constraints=[">=3.0.0"],
                    platforms=[Platform(os="linux", arch="amd64")],
                    max_versions=2,
                )
            ]
        )

        with patch("terraform_registry_stub.cache.AsyncRegistryClient", return_value=mock_client):
            await cache_providers(manifest, cache_dir)

        versions_file = cache_dir / "providers" / "hashicorp" / "null" / "versions.json"
        assert versions_file.exists()
        
        with open(versions_file) as f:
            cached_versions = json.load(f)
        assert cached_versions["id"] == "hashicorp/null"

        app = init_app(cache_dir)
        client = TestClient(app)

        response = client.get("/.well-known/terraform.json")
        assert response.status_code == 200
        assert "providers.v1" in response.json()

        response = client.get("/v1/providers/hashicorp/null/versions")
        assert response.status_code == 200
        data = response.json()
        assert data["id"] == "hashicorp/null"
        assert len(data["versions"]) == 2

        response = client.get("/v1/providers/hashicorp/null/3.2.0/download/linux/amd64")
        assert response.status_code == 200
        package_info = response.json()
        assert package_info["filename"] == "terraform-provider-null_3.2.0_linux_amd64.zip"
        assert package_info["os"] == "linux"
        assert package_info["arch"] == "amd64"

    def test_version_constraint_resolution(self, example_manifest):
        aws_provider = next(p for p in example_manifest.providers if p.type_ == "aws")
        
        from terraform_registry_stub.utils import resolve_versions
        
        available_versions = [
            "4.67.0", "5.0.0", "5.0.1", "5.1.0", "5.2.0", 
            "5.3.0", "5.4.0", "5.5.0", "5.6.0", "6.0.0"
        ]
        
        resolved = resolve_versions(
            available_versions=available_versions,
            constraints=aws_provider.version_constraints,
            include_prerelease=aws_provider.include_prerelease,
            max_versions=aws_provider.max_versions,
        )
        
        assert len(resolved) == 5
        assert "5.4.0" in resolved
        assert "5.3.0" in resolved
        assert "5.5.0" not in resolved
        assert "4.67.0" not in resolved

    def test_wildcard_version_with_max_limit(self, example_manifest):
        null_provider = next(p for p in example_manifest.providers if p.type_ == "null")
        
        from terraform_registry_stub.utils import resolve_versions
        
        available_versions = [f"3.{i}.0" for i in range(30)]
        
        resolved = resolve_versions(
            available_versions=available_versions,
            constraints=null_provider.version_constraints,
            max_versions=null_provider.max_versions,
        )
        
        assert len(resolved) == 20
        assert "3.29.0" in resolved
        assert "3.10.0" in resolved
        assert "3.9.0" not in resolved

    def test_latest_keyword_resolution(self, example_manifest):
        random_provider = next(p for p in example_manifest.providers if p.type_ == "random")
        
        from terraform_registry_stub.utils import resolve_versions
        
        available_versions = ["3.0.0", "3.1.0", "3.5.0", "3.4.0"]
        
        resolved = resolve_versions(
            available_versions=available_versions,
            constraints=random_provider.version_constraints,
        )
        
        assert len(resolved) == 1
        assert resolved[0] == "3.5.0"


class TestManifestValidation:
    def test_all_providers_parseable(self, example_manifest):
        for provider in example_manifest.providers:
            assert provider.namespace
            assert provider.type_
            assert provider.version_constraints
            assert provider.platforms

    def test_platform_configurations(self, example_manifest):
        aws_provider = next(p for p in example_manifest.providers if p.type_ == "aws")
        assert all(hasattr(p, 'os') and hasattr(p, 'arch') for p in aws_provider.platforms)
        
        random_provider = next(p for p in example_manifest.providers if p.type_ == "random")
        assert random_provider.platforms == ["*"]

    def test_null_provider_quoted_correctly(self, example_manifest_path):
        with open(example_manifest_path) as f:
            raw_yaml = yaml.safe_load(f)
        
        null_provider_data = next(
            p for p in raw_yaml["providers"] 
            if p["type"] == "null"
        )
        assert null_provider_data["type"] == "null"
        assert null_provider_data["type"] is not None
