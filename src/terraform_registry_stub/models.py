"""Pydantic models for manifest validation and data structures."""

import re

import semantic_version as semver
from pydantic import BaseModel, ConfigDict, Field, field_validator


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


class Platform(BaseModel):
    """Represents a target platform (OS/architecture combination)."""

    os: str
    arch: str


class Provider(BaseModel):
    """Provider specification with version constraints."""

    model_config = ConfigDict(populate_by_name=True)

    namespace: str
    type_: str = Field(alias="type")
    version_constraints: list[str] = Field(
        description="List of version constraints (OR logic: union of all constraints)"
    )
    platforms: list[Platform] | list[str] = Field(
        description="List of platforms or ['*'] for all available"
    )
    max_versions: int | None = Field(
        default=None,
        ge=1,
        description="Maximum number of versions to cache (newest first). None = unlimited",
    )
    include_prerelease: bool = Field(
        default=False, description="Include pre-release versions (alpha, beta, rc)"
    )

    @field_validator("version_constraints")
    @classmethod
    def validate_constraints(cls, v: list[str]) -> list[str]:
        """Validate version constraint syntax."""
        for constraint in v:
            if constraint in ["latest", "*"]:
                continue

            try:
                parsed = parse_terraform_constraint(constraint)
                if "!=" not in parsed:
                    semver.SimpleSpec(parsed)
            except ValueError as e:
                raise ValueError(f"Invalid version constraint '{constraint}': {e}") from e

        return v

    @field_validator("platforms")
    @classmethod
    def validate_platforms(cls, v: list[Platform] | list[str]) -> list[Platform] | list[str]:
        """Validate platform specifications."""
        if isinstance(v, list) and len(v) == 1 and v[0] == "*":
            return v

        platforms = []
        for p in v:
            if isinstance(p, dict):
                platforms.append(Platform(**p))
            elif isinstance(p, Platform):
                platforms.append(p)
            else:
                raise ValueError(f"Invalid platform specification: {p}")

        return platforms


class CacheOptions(BaseModel):
    """Global options for caching behavior."""

    download_packages: bool = Field(
        default=True, description="Download provider .zip files, checksums, and signatures"
    )
    verify_signatures: bool = Field(
        default=True, description="Verify GPG signatures on downloaded packages"
    )


class Manifest(BaseModel):
    """Root manifest configuration."""

    registry: str = Field(
        default="registry.terraform.io", description="Upstream Terraform registry hostname"
    )
    providers: list[Provider] = Field(description="List of providers to cache")
    cache_options: CacheOptions | None = Field(
        default_factory=CacheOptions, description="Global cache options"
    )

    @field_validator("registry")
    @classmethod
    def validate_registry(cls, v: str) -> str:
        """Validate and normalize registry hostname."""
        v = v.replace("https://", "").replace("http://", "")
        return v.rstrip("/")
