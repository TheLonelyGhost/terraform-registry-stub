import pytest

from terraform_registry_stub.utils import (
    ensure_directory,
    get_cache_path,
    get_versions_cache_path,
    is_prerelease,
    parse_terraform_constraint,
    parse_version_list,
    resolve_versions,
)


class TestParseTerraformConstraint:
    def test_pessimistic_operator(self):
        assert parse_terraform_constraint("~> 1.0.0") == "~= 1.0.0"

    def test_remove_comma_spaces(self):
        result = parse_terraform_constraint(">= 1.0.0, < 2.0.0")
        assert "," in result
        assert result.count(" ") < 3

    def test_combined_pessimistic_and_comma(self):
        result = parse_terraform_constraint("~> 1.0.0, < 2.0.0")
        assert "~=" in result
        assert "," in result

    def test_no_changes_needed(self):
        assert parse_terraform_constraint(">=1.0.0") == ">=1.0.0"


class TestParseVersionList:
    def test_parse_valid_versions(self):
        versions = parse_version_list(["1.0.0", "1.1.0", "2.0.0"])
        assert len(versions) == 3
        assert str(versions[0]) == "1.0.0"

    def test_exclude_prerelease_by_default(self):
        versions = parse_version_list(["1.0.0", "1.1.0-beta1", "2.0.0"])
        assert len(versions) == 2
        assert all("beta" not in str(v) for v in versions)

    def test_include_prerelease_when_enabled(self):
        versions = parse_version_list(["1.0.0", "1.1.0-beta1", "2.0.0"], include_prerelease=True)
        assert len(versions) == 3

    def test_skip_invalid_versions(self):
        versions = parse_version_list(["1.0.0", "invalid", "2.0.0"])
        assert len(versions) == 2


class TestResolveVersions:
    def test_latest_keyword(self):
        available = ["1.0.0", "2.0.0", "3.0.0"]
        result = resolve_versions(available, ["latest"])
        assert result == ["3.0.0"]

    def test_wildcard_all_versions(self):
        available = ["1.0.0", "2.0.0", "3.0.0"]
        result = resolve_versions(available, ["*"])
        assert result == ["3.0.0", "2.0.0", "1.0.0"]

    def test_wildcard_with_max_versions(self):
        available = ["1.0.0", "2.0.0", "3.0.0", "4.0.0"]
        result = resolve_versions(available, ["*"], max_versions=2)
        assert result == ["4.0.0", "3.0.0"]

    def test_simple_constraint(self):
        available = ["1.0.0", "2.0.0", "3.0.0"]
        result = resolve_versions(available, [">=2.0.0"])
        assert set(result) == {"2.0.0", "3.0.0"}

    def test_range_constraint(self):
        available = ["1.0.0", "2.0.0", "2.5.0", "3.0.0"]
        result = resolve_versions(available, [">=2.0.0,<3.0.0"])
        assert set(result) == {"2.0.0", "2.5.0"}

    def test_pessimistic_constraint(self):
        available = ["5.0.0", "5.0.1", "5.1.0", "6.0.0"]
        result = resolve_versions(available, [">=5.0.0,<5.1.0"])
        assert set(result) == {"5.0.0", "5.0.1"}

    def test_multiple_constraints_or_logic(self):
        available = ["4.0.0", "5.0.0", "5.5.0", "5.20.0", "6.0.0"]
        result = resolve_versions(available, [">=5.0.0,<5.10.0", ">=5.20.0,<5.30.0"])
        assert set(result) == {"5.0.0", "5.5.0", "5.20.0"}

    def test_exclude_prerelease_by_default(self):
        available = ["1.0.0", "2.0.0-beta1", "3.0.0"]
        result = resolve_versions(available, ["*"])
        assert "2.0.0-beta1" not in result

    def test_include_prerelease_when_enabled(self):
        available = ["1.0.0", "2.0.0-beta1", "3.0.0"]
        result = resolve_versions(available, ["*"], include_prerelease=True)
        assert "2.0.0-beta1" in result

    def test_not_equals_exclusion(self):
        available = ["1.0.0", "2.0.0", "3.0.0"]
        result = resolve_versions(available, [">=1.0.0", "!=2.0.0"])
        assert "2.0.0" not in result
        assert set(result) == {"3.0.0", "1.0.0"}

    def test_max_versions_limit(self):
        available = ["1.0.0", "2.0.0", "3.0.0", "4.0.0", "5.0.0"]
        result = resolve_versions(available, ["*"], max_versions=3)
        assert len(result) == 3
        assert result == ["5.0.0", "4.0.0", "3.0.0"]

    def test_no_matches_empty_list(self):
        available = ["1.0.0", "2.0.0"]
        result = resolve_versions(available, [">=5.0.0"])
        assert result == []

    def test_sorted_newest_first(self):
        available = ["1.0.0", "3.0.0", "2.0.0"]
        result = resolve_versions(available, ["*"])
        assert result == ["3.0.0", "2.0.0", "1.0.0"]


class TestIsPrerelease:
    def test_stable_version(self):
        assert is_prerelease("1.0.0") is False

    def test_beta_version(self):
        assert is_prerelease("1.0.0-beta1") is True

    def test_alpha_version(self):
        assert is_prerelease("1.0.0-alpha") is True

    def test_rc_version(self):
        assert is_prerelease("1.0.0-rc.1") is True

    def test_invalid_version(self):
        assert is_prerelease("invalid") is False


class TestEnsureDirectory:
    def test_creates_directory(self, tmp_path):
        new_dir = tmp_path / "new" / "nested" / "dir"
        ensure_directory(new_dir)
        assert new_dir.exists()
        assert new_dir.is_dir()

    def test_existing_directory_no_error(self, tmp_path):
        existing_dir = tmp_path / "existing"
        existing_dir.mkdir()
        ensure_directory(existing_dir)
        assert existing_dir.exists()


class TestGetCachePath:
    def test_path_structure(self, tmp_path):
        path = get_cache_path(tmp_path, "hashicorp", "aws", "5.0.0", "linux", "amd64")
        expected = tmp_path / "providers" / "hashicorp" / "aws" / "5.0.0" / "linux_amd64.json"
        assert path == expected

    def test_different_platform(self, tmp_path):
        path = get_cache_path(tmp_path, "hashicorp", "aws", "5.0.0", "windows", "arm64")
        assert path.name == "windows_arm64.json"


class TestGetVersionsCachePath:
    def test_versions_path_structure(self, tmp_path):
        path = get_versions_cache_path(tmp_path, "hashicorp", "aws")
        expected = tmp_path / "providers" / "hashicorp" / "aws" / "versions.json"
        assert path == expected

    def test_different_provider(self, tmp_path):
        path = get_versions_cache_path(tmp_path, "terraform-providers", "null")
        assert "terraform-providers" in str(path)
        assert "null" in str(path)
        assert path.name == "versions.json"
