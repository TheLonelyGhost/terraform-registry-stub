"""CLI command-line interface using argparse."""

import argparse
import asyncio
import sys
from pathlib import Path

import yaml
from rich.console import Console

from . import __version__
from .cache import cache_providers
from .models import Manifest
from .serve import run_server

console = Console()


def load_manifest(manifest_path: Path) -> Manifest:
    """Load and validate manifest from YAML file."""
    try:
        with open(manifest_path) as f:
            data = yaml.safe_load(f)
        return Manifest(**data)
    except FileNotFoundError:
        console.print(f"[red]Error: Manifest file not found: {manifest_path}[/red]")
        sys.exit(1)
    except yaml.YAMLError as e:
        console.print(f"[red]Error parsing YAML manifest: {e}[/red]")
        sys.exit(1)
    except Exception as e:
        console.print(f"[red]Error validating manifest: {e}[/red]")
        sys.exit(1)


def cmd_cache(args):
    """Execute the cache command."""
    manifest = load_manifest(args.manifest)
    output_dir = Path(args.output)

    download_packages = not args.no_packages

    if download_packages:
        manifest.cache_options.download_packages = True
    else:
        manifest.cache_options.download_packages = False

    asyncio.run(
        cache_providers(
            manifest=manifest,
            output_dir=output_dir,
            parallel=args.parallel,
            force=args.force,
        )
    )


def cmd_serve(args):
    """Execute the serve command."""
    cache_dir = Path(args.cache)

    if not cache_dir.exists():
        console.print(f"[red]Error: Cache directory does not exist: {cache_dir}[/red]")
        console.print("[yellow]Run 'cache' command first to create cache.[/yellow]")
        sys.exit(1)

    console.print("[green]Starting Terraform Registry Stub server...[/green]")
    console.print(f"[cyan]Cache directory: {cache_dir.absolute()}[/cyan]")
    console.print(f"[cyan]Server URL: http://{args.host}:{args.port}[/cyan]")
    console.print()
    console.print("[yellow]Configure Terraform to use this registry:[/yellow]")
    console.print()
    console.print("[dim]# ~/.terraformrc or terraform.rc[/dim]")
    console.print("[dim]provider_installation {[/dim]")
    console.print('[dim]  direct { exclude = ["registry.terraform.io/*/*"] }[/dim]')
    console.print(f'[dim]  network_mirror {{ url = "http://{args.host}:{args.port}/" }}[/dim]')
    console.print("[dim]}[/dim]")
    console.print()

    run_server(
        cache_dir=cache_dir,
        host=args.host,
        port=args.port,
        reload=args.reload,
    )


def main():
    """Main CLI entry point."""
    parser = argparse.ArgumentParser(
        prog="terraform-registry-stub",
        description="Cache and serve Terraform provider registry responses",
    )
    parser.add_argument(
        "--version",
        action="version",
        version=f"%(prog)s {__version__}",
    )

    subparsers = parser.add_subparsers(dest="command", help="Available commands")

    cache_parser = subparsers.add_parser(
        "cache",
        help="Cache providers from manifest",
    )
    cache_parser.add_argument(
        "-m",
        "--manifest",
        type=Path,
        required=True,
        help="Path to manifest YAML file",
    )
    cache_parser.add_argument(
        "-o",
        "--output",
        type=Path,
        default="./cache",
        help="Output directory for cache (default: ./cache)",
    )
    cache_parser.add_argument(
        "--no-packages",
        action="store_true",
        help="Skip downloading provider packages",
    )
    cache_parser.add_argument(
        "-p",
        "--parallel",
        type=int,
        default=4,
        help="Number of concurrent downloads (default: 4)",
    )
    cache_parser.add_argument(
        "--force",
        action="store_true",
        help="Force re-download even if cached",
    )
    cache_parser.set_defaults(func=cmd_cache)

    serve_parser = subparsers.add_parser(
        "serve",
        help="Run local HTTP server serving cached providers",
    )
    serve_parser.add_argument(
        "-c",
        "--cache",
        type=Path,
        default="./cache",
        help="Cache directory (default: ./cache)",
    )
    serve_parser.add_argument(
        "--host",
        type=str,
        default="127.0.0.1",
        help="Bind address (default: 127.0.0.1)",
    )
    serve_parser.add_argument(
        "-p",
        "--port",
        type=int,
        default=8080,
        help="Port number (default: 8080)",
    )
    serve_parser.add_argument(
        "--reload",
        action="store_true",
        help="Enable auto-reload for development",
    )
    serve_parser.set_defaults(func=cmd_serve)

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        sys.exit(1)

    args.func(args)


if __name__ == "__main__":
    main()
