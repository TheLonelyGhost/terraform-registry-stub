import json

import pytest
from fastapi.testclient import TestClient

from terraform_registry_stub.serve import app, init_app


@pytest.fixture
def client(setup_cached_provider):
    cache_dir = setup_cached_provider["cache_dir"]
    init_app(cache_dir)
    return TestClient(app)


class TestServiceDiscovery:
    def test_service_discovery_endpoint(self, client):
        response = client.get("/.well-known/terraform.json")
        assert response.status_code == 200
        data = response.json()
        assert "providers.v1" in data
        assert data["providers.v1"] == "/v1/providers/"


class TestGetProviderVersions:
    def test_get_provider_versions_success(self, client, setup_cached_provider):
        namespace = setup_cached_provider["namespace"]
        type_ = setup_cached_provider["type"]

        response = client.get(f"/v1/providers/{namespace}/{type_}/versions")
        assert response.status_code == 200
        data = response.json()
        assert "versions" in data
        assert data["id"] == "hashicorp/aws"

    def test_get_provider_versions_not_found(self, client):
        response = client.get("/v1/providers/unknown/unknown/versions")
        assert response.status_code == 404

    def test_get_provider_versions_returns_json(self, client, setup_cached_provider):
        namespace = setup_cached_provider["namespace"]
        type_ = setup_cached_provider["type"]

        response = client.get(f"/v1/providers/{namespace}/{type_}/versions")
        assert response.headers["content-type"] == "application/json"


class TestGetProviderPackage:
    def test_get_provider_package_success(self, client, setup_cached_provider):
        namespace = setup_cached_provider["namespace"]
        type_ = setup_cached_provider["type"]
        version = setup_cached_provider["version"]
        os = setup_cached_provider["os"]
        arch = setup_cached_provider["arch"]

        response = client.get(f"/v1/providers/{namespace}/{type_}/{version}/download/{os}/{arch}")
        assert response.status_code == 200
        data = response.json()
        assert "filename" in data
        assert data["os"] == os
        assert data["arch"] == arch

    def test_get_provider_package_not_found(self, client):
        response = client.get("/v1/providers/unknown/unknown/1.0.0/download/linux/amd64")
        assert response.status_code == 404

    def test_get_provider_package_url_rewriting(self, client, setup_cached_provider):
        namespace = setup_cached_provider["namespace"]
        type_ = setup_cached_provider["type"]
        version = setup_cached_provider["version"]
        os = setup_cached_provider["os"]
        arch = setup_cached_provider["arch"]

        response = client.get(f"/v1/providers/{namespace}/{type_}/{version}/download/{os}/{arch}")
        data = response.json()

        assert data["download_url"].startswith("/v1/providers/")
        assert not data["download_url"].startswith("https://")


class TestDownloadPackageFile:
    def test_download_package_file_success(self, client, setup_cached_provider):
        namespace = setup_cached_provider["namespace"]
        type_ = setup_cached_provider["type"]
        version = setup_cached_provider["version"]
        filename = "terraform-provider-aws_5.0.0_linux_amd64.zip"

        response = client.get(f"/v1/providers/{namespace}/{type_}/{version}/packages/{filename}")
        assert response.status_code == 200
        assert response.content == b"fake-zip"

    def test_download_package_file_not_found(self, client, setup_cached_provider):
        namespace = setup_cached_provider["namespace"]
        type_ = setup_cached_provider["type"]
        version = setup_cached_provider["version"]

        response = client.get(f"/v1/providers/{namespace}/{type_}/{version}/packages/nonexistent.zip")
        assert response.status_code == 404


class TestServerInitialization:
    def test_init_app_sets_cache_directory(self, tmp_cache_dir):
        from terraform_registry_stub.serve import cache_directory

        result = init_app(tmp_cache_dir)
        assert result is app

    def test_uninitialized_cache_directory_error(self):
        from terraform_registry_stub.serve import cache_directory
        import terraform_registry_stub.serve as serve_module

        serve_module.cache_directory = None

        client = TestClient(app)
        response = client.get("/v1/providers/hashicorp/aws/versions")
        assert response.status_code == 500
