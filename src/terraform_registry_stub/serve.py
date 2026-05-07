"""Serve command implementation for running the local registry server."""

import json
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse, JSONResponse

from .utils import get_cache_path, get_versions_cache_path

app = FastAPI(title="Terraform Registry Stub", version="0.1.0")

cache_directory: Path | None = None


def init_app(cache_dir: Path) -> FastAPI:
    """Initialize the FastAPI app with cache directory."""
    global cache_directory
    cache_directory = cache_dir
    return app


@app.get("/.well-known/terraform.json")
async def service_discovery():
    """Service discovery endpoint for Terraform."""
    return {
        "providers.v1": "/v1/providers/",
    }


@app.get("/v1/providers/{namespace}/{type}/versions")
async def get_provider_versions(namespace: str, type: str):
    """Get available versions for a provider."""
    if cache_directory is None:
        raise HTTPException(status_code=500, detail="Cache directory not initialized")

    versions_path = get_versions_cache_path(cache_directory, namespace, type)

    if not versions_path.exists():
        raise HTTPException(status_code=404, detail="Provider not found in cache")

    with open(versions_path) as f:
        data = json.load(f)

    return JSONResponse(content=data)


@app.get("/v1/providers/{namespace}/{type}/{version}/download/{os}/{arch}")
async def get_provider_package(namespace: str, type: str, version: str, os: str, arch: str):
    """Get package metadata for a specific provider version/platform."""
    if cache_directory is None:
        raise HTTPException(status_code=500, detail="Cache directory not initialized")

    package_path = get_cache_path(cache_directory, namespace, type, version, os, arch)

    if not package_path.exists():
        raise HTTPException(status_code=404, detail="Provider package not found in cache")

    with open(package_path) as f:
        data = json.load(f)

    packages_dir = package_path.parent / "packages"
    if packages_dir.exists():
        filename = data.get("filename")
        if filename:
            local_zip_path = packages_dir / filename
            if local_zip_path.exists():
                data["download_url"] = (
                    f"/v1/providers/{namespace}/{type}/{version}/packages/{filename}"
                )

            shasums_filename = f"{filename.replace('.zip', '')}_SHA256SUMS"
            local_shasums_path = packages_dir / shasums_filename
            if local_shasums_path.exists():
                data["shasums_url"] = (
                    f"/v1/providers/{namespace}/{type}/{version}/packages/{shasums_filename}"
                )

            sig_filename = f"{shasums_filename}.sig"
            local_sig_path = packages_dir / sig_filename
            if local_sig_path.exists():
                data["shasums_signature_url"] = (
                    f"/v1/providers/{namespace}/{type}/{version}/packages/{sig_filename}"
                )

    return JSONResponse(content=data)


@app.get("/v1/providers/{namespace}/{type}/{version}/packages/{filename}")
async def download_package_file(namespace: str, type: str, version: str, filename: str):
    """Download a cached provider package file."""
    if cache_directory is None:
        raise HTTPException(status_code=500, detail="Cache directory not initialized")

    packages_dir = cache_directory / "providers" / namespace / type / version / "packages"
    file_path = packages_dir / filename

    if not file_path.exists():
        raise HTTPException(status_code=404, detail="File not found")

    return FileResponse(file_path)


def run_server(
    cache_dir: Path,
    host: str = "127.0.0.1",
    port: int = 8080,
    reload: bool = False,
) -> None:
    """
    Run the FastAPI server.

    Args:
        cache_dir: Directory containing cached provider data
        host: Host to bind to
        port: Port to bind to
        reload: Enable auto-reload for development
    """
    import uvicorn

    init_app(cache_dir)

    uvicorn.run(
        "terraform_registry_stub.serve:app",
        host=host,
        port=port,
        reload=reload,
        log_level="info",
    )
