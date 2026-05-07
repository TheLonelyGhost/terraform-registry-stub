import json
from pathlib import Path

import pytest


@pytest.fixture
def tmp_cache_dir(tmp_path):
    cache_dir = tmp_path / "cache"
    cache_dir.mkdir()
    return cache_dir


@pytest.fixture
def sample_provider_versions():
    return {
        "id": "hashicorp/aws",
        "versions": [
            {"version": "5.20.0", "platforms": [{"os": "linux", "arch": "amd64"}]},
            {"version": "5.10.0", "platforms": [{"os": "linux", "arch": "amd64"}]},
            {"version": "5.0.0", "platforms": [{"os": "linux", "arch": "amd64"}]},
            {"version": "4.67.0", "platforms": [{"os": "linux", "arch": "amd64"}]},
            {"version": "5.0.0-beta1", "platforms": [{"os": "linux", "arch": "amd64"}]},
        ],
    }


@pytest.fixture
def sample_package_metadata():
    return {
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


@pytest.fixture
def sample_manifest_dict():
    return {
        "registry": "registry.terraform.io",
        "providers": [
            {
                "namespace": "hashicorp",
                "type": "aws",
                "version_constraints": [">=5.0.0,<6.0.0"],
                "platforms": [{"os": "linux", "arch": "amd64"}],
                "max_versions": 5,
                "include_prerelease": False,
            }
        ],
        "cache_options": {"download_packages": True, "verify_signatures": True},
    }


@pytest.fixture
def setup_cached_provider(tmp_cache_dir, sample_provider_versions, sample_package_metadata):
    namespace = "hashicorp"
    type_ = "aws"
    version = "5.0.0"
    os = "linux"
    arch = "amd64"

    provider_dir = tmp_cache_dir / "providers" / namespace / type_
    provider_dir.mkdir(parents=True)

    versions_path = provider_dir / "versions.json"
    with open(versions_path, "w") as f:
        json.dump(sample_provider_versions, f)

    version_dir = provider_dir / version
    version_dir.mkdir()

    package_path = version_dir / f"{os}_{arch}.json"
    with open(package_path, "w") as f:
        json.dump(sample_package_metadata, f)

    packages_dir = version_dir / "packages"
    packages_dir.mkdir()
    (packages_dir / "terraform-provider-aws_5.0.0_linux_amd64.zip").write_bytes(b"fake-zip")

    return {
        "cache_dir": tmp_cache_dir,
        "namespace": namespace,
        "type": type_,
        "version": version,
        "os": os,
        "arch": arch,
    }
