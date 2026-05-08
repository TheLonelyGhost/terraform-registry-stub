from terraform_registry_stub.client import AsyncRegistryClient


class TestAsyncRegistryClient:
    def test_initialization(self):
        client = AsyncRegistryClient()
        assert client.base_url == "https://registry.terraform.io"
        assert client.timeout.connect == 10.0

    def test_custom_base_url(self):
        client = AsyncRegistryClient(base_url="https://custom.registry.com")
        assert client.base_url == "https://custom.registry.com"

    def test_base_url_trailing_slash_removed(self):
        client = AsyncRegistryClient(base_url="https://registry.terraform.io/")
        assert client.base_url == "https://registry.terraform.io"

    def test_custom_timeout(self):
        client = AsyncRegistryClient(timeout=60.0)
        assert client.timeout.connect == 10.0

    def test_get_base_api_url(self):
        client = AsyncRegistryClient()
        assert client._get_base_api_url() == "https://registry.terraform.io/v1/providers"
