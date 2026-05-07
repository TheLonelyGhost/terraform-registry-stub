"""Utility functions for version resolution and file operations."""

import re
from pathlib import Path

import semantic_version as semver


def parse_terraform_constraint(constraint: str) -> str:
    """
    Convert Terraform version constraint syntax to semantic-version syntax.

    Terraform uses:
    - ~> 1.0.0 (pessimistic)
    - >= 1.0.0, < 2.0.0 (comma-separated AND)

    semantic-version uses:
    - ~=1.0.0 (compatible release)
    - >=1.0.0,<2.0.0 (comma-separated AND, no spaces)
    """
    if "~>" in constraint:
        constraint = constraint.replace("~>", "~=")

    constraint = re.sub(r"\s*,\s*", ",", constraint)

    return constraint.strip()


def parse_version_list(
    version_strings: list[str], include_prerelease: bool = False
) -> list[semver.Version]:
    """
    Parse a list of version strings into Version objects.

    Args:
        version_strings: List of version strings to parse
        include_prerelease: Whether to include pre-release versions

    Returns:
        List of parsed Version objects
    """
    versions = []
    for v in version_strings:
        try:
            version = semver.Version(v)
            if not include_prerelease and version.prerelease:
                continue
            versions.append(version)
        except ValueError:
            continue
    return versions


def resolve_versions(
    available_versions: list[str],
    constraints: list[str],
    include_prerelease: bool = False,
    max_versions: int | None = None,
) -> list[str]:
    """
    Resolve which versions match the given constraints using OR logic.

    Args:
        available_versions: List of all available version strings from registry
        constraints: List of version constraint expressions (OR logic - union)
        include_prerelease: Whether to include pre-release versions
        max_versions: Maximum number of versions to return (newest first)

    Returns:
        Sorted list of matching version strings (newest first)
    """
    if "latest" in constraints:
        versions = parse_version_list(available_versions, include_prerelease)
        if not versions:
            return []
        latest = max(versions)
        return [str(latest)]

    if "*" in constraints:
        versions = parse_version_list(available_versions, include_prerelease)
        versions.sort(reverse=True)
        result = [str(v) for v in versions]
        if max_versions:
            result = result[:max_versions]
        return result

    parsed_versions = parse_version_list(available_versions, include_prerelease)

    matching_versions: set[semver.Version] = set()
    exclusions: set[str] = set()

    for constraint_expr in constraints:
        if "!=" in constraint_expr:
            excluded_version = constraint_expr.split("!=")[1].strip()
            exclusions.add(excluded_version)
            continue

        parsed_constraint = parse_terraform_constraint(constraint_expr)
        spec = semver.SimpleSpec(parsed_constraint)

        for version in parsed_versions:
            if version in spec:
                matching_versions.add(version)

    matching_versions = {v for v in matching_versions if str(v) not in exclusions}

    sorted_versions = sorted(matching_versions, reverse=True)

    if max_versions:
        sorted_versions = sorted_versions[:max_versions]

    return [str(v) for v in sorted_versions]


def is_prerelease(version_string: str) -> bool:
    """Check if a version string is a pre-release version."""
    try:
        version = semver.Version(version_string)
        return bool(version.prerelease)
    except ValueError:
        return False


def ensure_directory(path: Path) -> None:
    """Ensure a directory exists, creating it if necessary."""
    path.mkdir(parents=True, exist_ok=True)


def get_cache_path(
    cache_dir: Path, namespace: str, type_: str, version: str, os: str, arch: str
) -> Path:
    """
    Get the cache file path for a provider package.

    Args:
        cache_dir: Base cache directory
        namespace: Provider namespace
        type_: Provider type
        version: Provider version
        os: Operating system
        arch: Architecture

    Returns:
        Path to the cache file
    """
    provider_dir = cache_dir / "providers" / namespace / type_ / version
    return provider_dir / f"{os}_{arch}.json"


def get_versions_cache_path(cache_dir: Path, namespace: str, type_: str) -> Path:
    """
    Get the cache file path for provider versions list.

    Args:
        cache_dir: Base cache directory
        namespace: Provider namespace
        type_: Provider type

    Returns:
        Path to the versions cache file
    """
    return cache_dir / "providers" / namespace / type_ / "versions.json"
