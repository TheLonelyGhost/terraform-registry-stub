# Terraform Registry Stub

A CLI tool to cache and serve Terraform Provider registry responses for offline or air-gapped environments.

**Requirements**: Python 3.11 or later

## Features

- 🚀 **Cache providers** from upstream Terraform Registry
- 📦 **Download provider packages** (.zip files, checksums, signatures)
- 🌐 **Serve cached responses** via local HTTP server
- ⚡ **Fast parallel downloads** using async HTTP client
- 🎨 **Beautiful progress bars** powered by Rich
- ✅ **GPG signature verification** for security
- 📝 **YAML manifest** for easy configuration
- 🔍 **Version constraints** using Terraform syntax

## Installation

### Using uv (recommended)

```bash
# Clone the repository
git clone https://github.com/TheLonelyGhost/terraform-registry-stub.git
cd terraform-registry-stub

# Create virtual environment and install
uv venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate
uv pip install -e .
```

### Using pip

```bash
pip install -e .
```

## Quick Start

### 1. Create a manifest file

Create `manifest.yaml`:

```yaml
registry: registry.terraform.io

providers:
  - namespace: hashicorp
    type: aws
    version_constraints:
      - ">= 5.0.0, < 5.10.0"
    platforms:
      - os: linux
        arch: amd64
      - os: darwin
        arch: arm64
    max_versions: 10
  
  - namespace: hashicorp
    type: random
    version_constraints:
      - "latest"
    platforms: ["*"]

cache_options:
  download_packages: true
  verify_signatures: true
```

### 2. Cache providers

```bash
# Using installed command
terraform-registry-stub cache --manifest manifest.yaml --output ./cache

# Or using python -m
python3 -m terraform_registry_stub cache --manifest manifest.yaml --output ./cache
```

### 3. Serve cached registry

```bash
# Using installed command
terraform-registry-stub serve --cache ./cache --port 8080

# Or using python -m
python3 -m terraform_registry_stub serve --cache ./cache --port 8080
```

### 4. Configure Terraform

Create or edit `~/.terraformrc`:

```hcl
provider_installation {
  direct {
    exclude = ["registry.terraform.io/*/*"]
  }
  network_mirror {
    url = "http://localhost:8080/"
  }
}
```

## Usage

Both commands can be invoked using the installed command or via `python3 -m`:

```bash
# Using installed command
terraform-registry-stub cache -m manifest.yaml -o ./cache

# Or using python -m (useful when not in PATH)
python3 -m terraform_registry_stub cache -m manifest.yaml -o ./cache
```

### Cache Command

```bash
terraform-registry-stub cache [OPTIONS]
# or: python3 -m terraform_registry_stub cache [OPTIONS]

Options:
  -m, --manifest PATH    Path to manifest YAML file [required]
  -o, --output PATH      Output directory for cache [default: ./cache]
  --no-packages          Skip downloading provider packages
  -p, --parallel INT     Number of concurrent downloads [default: 4]
  --force                Force re-download even if cached
  -h, --help             Show this message and exit
```

### Serve Command

```bash
terraform-registry-stub serve [OPTIONS]
# or: python3 -m terraform_registry_stub serve [OPTIONS]

Options:
  -c, --cache PATH       Cache directory [default: ./cache]
  --host TEXT            Bind address [default: 127.0.0.1]
  -p, --port INT         Port number [default: 8080]
  --proxy-missing        Proxy uncached requests to upstream
  --reload               Enable auto-reload for development
  -h, --help             Show this message and exit
```

## Manifest Format

### Version Constraints

Use Terraform's version constraint syntax:

- `= 1.0.0` - Exact version
- `!= 1.0.0` - Exclude version
- `> 1.0.0`, `>= 1.0.0` - Greater than (or equal)
- `< 1.0.0`, `<= 1.0.0` - Less than (or equal)
- `~> 1.0` - Pessimistic constraint (>= 1.0, < 2.0)
- `~> 1.0.0` - Pessimistic constraint (>= 1.0.0, < 1.1.0)
- Multiple constraints: `>= 1.0.0, < 2.0.0`

### Special Keywords

- `latest` - Only cache the newest version
- `*` - Cache all available versions

### Example Manifest

```yaml
registry: registry.terraform.io

providers:
  # Cache a range of versions
  - namespace: hashicorp
    type: aws
    version_constraints:
      - ">= 5.0.0, < 5.10.0"
      - "~> 5.20.0"  # OR logic: also include 5.20.x
    platforms:
      - os: linux
        arch: amd64
    max_versions: 10  # Limit to 10 newest
    include_prerelease: false

  # Cache latest version only
  - namespace: hashicorp
    type: random
    version_constraints:
      - "latest"
    platforms: ["*"]  # All available platforms

  # Cache all versions (with limit)
  - namespace: hashicorp
    type: null
    version_constraints:
      - "*"
    platforms:
      - os: linux
        arch: amd64
    max_versions: 20  # Safety limit

cache_options:
  download_packages: true   # Download .zip files
  verify_signatures: true   # Verify GPG signatures
```

## Development

### Setup development environment

```bash
# Install with dev dependencies
uv pip install -e ".[dev]"
```

### Run tests

```bash
uv run pytest
```

### Lint and format code

```bash
# Format code with ruff
uv run ruff format src/ tests/

# Check formatting without modifying files
uv run ruff format --check src/ tests/

# Lint and auto-fix with ruff
uv run ruff check --fix src/ tests/

# Check without auto-fixing
uv run ruff check src/ tests/
```

## License

MIT License - see LICENSE file for details.
