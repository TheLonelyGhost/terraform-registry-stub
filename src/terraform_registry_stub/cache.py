"""Cache command implementation for downloading and storing provider data."""

import asyncio
import json
from pathlib import Path
from typing import Any

from rich.console import Console
from rich.panel import Panel
from rich.progress import (
    BarColumn,
    Progress,
    SpinnerColumn,
    TaskProgressColumn,
    TextColumn,
    TimeRemainingColumn,
)
from rich.table import Table

from .client import AsyncRegistryClient
from .models import Manifest, Platform, Provider
from .utils import ensure_directory, get_cache_path, get_versions_cache_path, resolve_versions

console = Console()


async def cache_providers(
    manifest: Manifest, output_dir: Path, parallel: int = 4, force: bool = False
) -> None:
    """
    Cache providers from manifest with concurrent downloads.

    Args:
        manifest: Parsed manifest configuration
        output_dir: Directory to store cached files
        parallel: Number of concurrent downloads
        force: Force re-download even if cached
    """
    console.print(Panel.fit("📦 Caching Terraform Providers", style="bold blue"))

    client = AsyncRegistryClient(f"https://{manifest.registry}")
    output_dir.mkdir(parents=True, exist_ok=True)

    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        BarColumn(),
        TaskProgressColumn(),
        TimeRemainingColumn(),
        console=console,
    ) as progress:
        semaphore = asyncio.Semaphore(parallel)

        tasks = []
        for provider in manifest.providers:
            task = cache_provider_with_semaphore(
                client=client,
                provider=provider,
                output_dir=output_dir,
                download_packages=manifest.cache_options.download_packages,
                verify_signatures=manifest.cache_options.verify_signatures,
                force=force,
                progress=progress,
                semaphore=semaphore,
            )
            tasks.append(task)

        results = await asyncio.gather(*tasks, return_exceptions=True)

        report_cache_results(results)


async def cache_provider_with_semaphore(
    client: AsyncRegistryClient,
    provider: Provider,
    output_dir: Path,
    download_packages: bool,
    verify_signatures: bool,
    force: bool,
    progress: Progress,
    semaphore: asyncio.Semaphore,
) -> dict[str, Any]:
    """Cache a provider with semaphore for rate limiting."""
    async with semaphore:
        return await cache_provider(
            client=client,
            provider=provider,
            output_dir=output_dir,
            download_packages=download_packages,
            verify_signatures=verify_signatures,
            force=force,
            progress=progress,
        )


async def cache_provider(
    client: AsyncRegistryClient,
    provider: Provider,
    output_dir: Path,
    download_packages: bool,
    verify_signatures: bool,
    force: bool,
    progress: Progress,
) -> dict[str, Any]:
    """
    Cache a single provider with version constraint resolution.

    Returns:
        Dictionary with cache results for reporting
    """
    provider_id = f"{provider.namespace}/{provider.type_}"

    task_id = progress.add_task(f"[cyan]Resolving {provider_id}...", total=None)

    try:
        versions_response = await client.get_provider_versions(provider.namespace, provider.type_)

        available_versions = [v["version"] for v in versions_response["versions"]]

        matching_versions = resolve_versions(
            available_versions=available_versions,
            constraints=provider.version_constraints,
            include_prerelease=provider.include_prerelease,
            max_versions=provider.max_versions,
        )

        if not matching_versions:
            progress.update(
                task_id, description=f"[yellow]No matches: {provider_id}", completed=True
            )
            return {"provider": provider_id, "status": "no_matches", "versions": 0, "packages": 0}

        version_summary = ", ".join(matching_versions[:3])
        if len(matching_versions) > 3:
            version_summary += f" ... (+{len(matching_versions) - 3} more)"

        console.print(
            f"[green]✓[/green] {provider_id}: {len(matching_versions)} versions [{version_summary}]"
        )

        versions_cache_path = get_versions_cache_path(
            output_dir, provider.namespace, provider.type_
        )
        ensure_directory(versions_cache_path.parent)
        with open(versions_cache_path, "w") as f:
            json.dump(versions_response, f, indent=2)

        platforms = await resolve_platforms(
            provider=provider,
            versions_response=versions_response,
            matching_versions=matching_versions,
        )

        total_packages = len(matching_versions) * len(platforms)
        progress.update(
            task_id, description=f"[cyan]Caching {provider_id}", total=total_packages, completed=0
        )

        cached_count = 0
        for version in matching_versions:
            for platform in platforms:
                await cache_provider_package(
                    client=client,
                    namespace=provider.namespace,
                    type_=provider.type_,
                    version=version,
                    os=platform.os,
                    arch=platform.arch,
                    output_dir=output_dir,
                    download_packages=download_packages,
                    verify_signatures=verify_signatures,
                    force=force,
                )
                cached_count += 1
                progress.update(task_id, completed=cached_count)

        progress.update(
            task_id, description=f"[green]✓ Cached {provider_id}", completed=total_packages
        )

        return {
            "provider": provider_id,
            "status": "success",
            "versions": len(matching_versions),
            "packages": total_packages,
        }

    except Exception as e:
        progress.update(task_id, description=f"[red]✗ Failed: {provider_id}", completed=True)
        console.print(f"[red]Error caching {provider_id}: {e}[/red]")
        return {"provider": provider_id, "status": "error", "error": str(e)}


async def resolve_platforms(
    provider: Provider, versions_response: dict[str, Any], matching_versions: list[str]
) -> list[Platform]:
    """Resolve platform list (handle wildcard)."""
    if provider.platforms == ["*"]:
        all_platforms = set()
        for version_info in versions_response["versions"]:
            if version_info["version"] in matching_versions:
                for platform in version_info.get("platforms", []):
                    all_platforms.add((platform["os"], platform["arch"]))
        return [Platform(os=os, arch=arch) for os, arch in sorted(all_platforms)]
    return [p if isinstance(p, Platform) else Platform(**p) for p in provider.platforms]


async def cache_provider_package(
    client: AsyncRegistryClient,
    namespace: str,
    type_: str,
    version: str,
    os: str,
    arch: str,
    output_dir: Path,
    download_packages: bool,
    verify_signatures: bool,
    force: bool,
) -> None:
    """Cache a specific provider version/platform package."""
    cache_path = get_cache_path(output_dir, namespace, type_, version, os, arch)

    if cache_path.exists() and not force:
        return

    ensure_directory(cache_path.parent)

    package_info = await client.get_provider_package(namespace, type_, version, os, arch)

    with open(cache_path, "w") as f:
        json.dump(package_info, f, indent=2)

    if download_packages:
        packages_dir = cache_path.parent / "packages"
        ensure_directory(packages_dir)

        filename = package_info.get(
            "filename", f"terraform-provider-{type_}_{version}_{os}_{arch}.zip"
        )
        zip_path = packages_dir / filename

        if not zip_path.exists() or force:
            await client.download_file(package_info["download_url"], zip_path)

        if verify_signatures:
            shasums_filename = f"{filename.replace('.zip', '')}_SHA256SUMS"
            shasums_path = packages_dir / shasums_filename
            if not shasums_path.exists() or force:
                await client.download_file(package_info["shasums_url"], shasums_path)

            sig_filename = f"{shasums_filename}.sig"
            sig_path = packages_dir / sig_filename
            if not sig_path.exists() or force:
                await client.download_file(package_info["shasums_signature_url"], sig_path)


def report_cache_results(results: list[Any]) -> None:
    """Display summary table of cache results."""
    table = Table(title="Cache Summary")
    table.add_column("Provider", style="cyan")
    table.add_column("Status", style="green")
    table.add_column("Versions", justify="right")
    table.add_column("Packages", justify="right")

    total_versions = 0
    total_packages = 0

    for result in results:
        if isinstance(result, Exception):
            continue

        status_icon = {"success": "✓", "no_matches": "⚠", "error": "✗"}.get(result["status"], "?")

        table.add_row(
            result["provider"],
            status_icon,
            str(result.get("versions", 0)),
            str(result.get("packages", 0)),
        )

        total_versions += result.get("versions", 0)
        total_packages += result.get("packages", 0)

    console.print(table)
    console.print(
        f"\n[bold green]Total: {total_packages} packages from {total_versions} versions[/bold green]"
    )
