import pytest
from pydantic import ValidationError

from terraform_registry_stub.models import (
    CacheOptions,
    Manifest,
    Platform,
    Provider,
    parse_terraform_constraint,
)


class TestParseTerraformConstraint:
    def test_pessimistic_operator_conversion(self):
        assert parse_terraform_constraint("~> 1.0.0") == "~= 1.0.0"

    def test_comma_space_removal(self):
        result = parse_terraform_constraint(">= 1.0.0, < 2.0.0")
        assert "," in result
        assert result.count(" ") < 3

    def test_already_valid_format(self):
        assert parse_terraform_constraint(">=1.0.0") == ">=1.0.0"

    def test_combined_pessimistic_and_spaces(self):
        result = parse_terraform_constraint("~> 1.0.0, < 2.0.0")
        assert "~=" in result
        assert "," in result


class TestPlatform:
    def test_valid_platform(self):
        platform = Platform(os="linux", arch="amd64")
        assert platform.os == "linux"
        assert platform.arch == "amd64"

    def test_platform_dict_conversion(self):
        data = {"os": "windows", "arch": "arm64"}
        platform = Platform(**data)
        assert platform.os == "windows"
        assert platform.arch == "arm64"


class TestProvider:
    def test_valid_provider_basic(self):
        provider = Provider(
            namespace="hashicorp",
            type="aws",
            version_constraints=[">=5.0.0"],
            platforms=[Platform(os="linux", arch="amd64")],
        )
        assert provider.namespace == "hashicorp"
        assert provider.type_ == "aws"
        assert provider.version_constraints == [">=5.0.0"]
        assert len(provider.platforms) == 1

    def test_type_field_alias(self):
        data = {
            "namespace": "hashicorp",
            "type": "aws",
            "version_constraints": ["latest"],
            "platforms": ["*"],
        }
        provider = Provider(**data)
        assert provider.type_ == "aws"

    def test_multiple_version_constraints(self):
        provider = Provider(
            namespace="hashicorp",
            type="aws",
            version_constraints=[">=5.0.0,<5.10.0", ">=5.20.0"],
            platforms=["*"],
        )
        assert len(provider.version_constraints) == 2

    def test_latest_keyword(self):
        provider = Provider(
            namespace="hashicorp",
            type="aws",
            version_constraints=["latest"],
            platforms=["*"],
        )
        assert provider.version_constraints == ["latest"]

    def test_wildcard_version(self):
        provider = Provider(
            namespace="hashicorp",
            type="aws",
            version_constraints=["*"],
            platforms=["*"],
        )
        assert provider.version_constraints == ["*"]

    def test_wildcard_platforms(self):
        provider = Provider(
            namespace="hashicorp",
            type="aws",
            version_constraints=["latest"],
            platforms=["*"],
        )
        assert provider.platforms == ["*"]

    def test_max_versions_validation(self):
        with pytest.raises(ValidationError):
            Provider(
                namespace="hashicorp",
                type="aws",
                version_constraints=["*"],
                platforms=["*"],
                max_versions=0,
            )

    def test_invalid_version_constraint(self):
        with pytest.raises(ValidationError, match="Invalid version constraint"):
            Provider(
                namespace="hashicorp",
                type="aws",
                version_constraints=["invalid!!!"],
                platforms=["*"],
            )

    def test_prerelease_default_false(self):
        provider = Provider(
            namespace="hashicorp",
            type="aws",
            version_constraints=["*"],
            platforms=["*"],
        )
        assert provider.include_prerelease is False

    def test_prerelease_explicit_true(self):
        provider = Provider(
            namespace="hashicorp",
            type="aws",
            version_constraints=["*"],
            platforms=["*"],
            include_prerelease=True,
        )
        assert provider.include_prerelease is True

    def test_max_versions_none_unlimited(self):
        provider = Provider(
            namespace="hashicorp",
            type="aws",
            version_constraints=["*"],
            platforms=["*"],
            max_versions=None,
        )
        assert provider.max_versions is None


class TestCacheOptions:
    def test_defaults(self):
        options = CacheOptions()
        assert options.download_packages is True
        assert options.verify_signatures is True

    def test_explicit_values(self):
        options = CacheOptions(download_packages=False, verify_signatures=False)
        assert options.download_packages is False
        assert options.verify_signatures is False


class TestManifest:
    def test_valid_manifest(self, sample_manifest_dict):
        manifest = Manifest(**sample_manifest_dict)
        assert manifest.registry == "registry.terraform.io"
        assert len(manifest.providers) == 1
        if manifest.cache_options:
            assert manifest.cache_options.download_packages is True

    def test_default_registry(self):
        manifest = Manifest(
            providers=[
                Provider(
                    namespace="hashicorp",
                    type="aws",
                    version_constraints=["latest"],
                    platforms=["*"],
                )
            ]
        )
        assert manifest.registry == "registry.terraform.io"

    def test_registry_https_stripping(self):
        manifest = Manifest(
            registry="https://registry.terraform.io/",
            providers=[
                Provider(
                    namespace="hashicorp",
                    type="aws",
                    version_constraints=["latest"],
                    platforms=["*"],
                )
            ],
        )
        assert manifest.registry == "registry.terraform.io"

    def test_registry_http_stripping(self):
        manifest = Manifest(
            registry="http://registry.terraform.io",
            providers=[
                Provider(
                    namespace="hashicorp",
                    type="aws",
                    version_constraints=["latest"],
                    platforms=["*"],
                )
            ],
        )
        assert manifest.registry == "registry.terraform.io"

    def test_registry_trailing_slash_removal(self):
        manifest = Manifest(
            registry="registry.terraform.io/",
            providers=[
                Provider(
                    namespace="hashicorp",
                    type="aws",
                    version_constraints=["latest"],
                    platforms=["*"],
                )
            ],
        )
        assert manifest.registry == "registry.terraform.io"

    def test_cache_options_default_factory(self):
        manifest = Manifest(
            providers=[
                Provider(
                    namespace="hashicorp",
                    type="aws",
                    version_constraints=["latest"],
                    platforms=["*"],
                )
            ]
        )
        assert manifest.cache_options is not None
        assert manifest.cache_options.download_packages is True

    def test_empty_providers_list(self):
        manifest = Manifest(providers=[])
        assert len(manifest.providers) == 0

    def test_multiple_providers(self):
        manifest = Manifest(
            providers=[
                Provider(
                    namespace="hashicorp",
                    type="aws",
                    version_constraints=["latest"],
                    platforms=["*"],
                ),
                Provider(
                    namespace="hashicorp",
                    type="random",
                    version_constraints=["*"],
                    platforms=[Platform(os="linux", arch="amd64")],
                ),
            ]
        )
        assert len(manifest.providers) == 2
