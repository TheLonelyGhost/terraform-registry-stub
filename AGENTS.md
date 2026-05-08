# Agent Instructions

## Project Overview

Python 3.11+ CLI tool for caching and serving Terraform provider registry responses. Uses `uv` for package management.

## Development Commands

```bash
# Install with dev dependencies
uv pip install -e ".[dev]"

# Run tests (required before commits)
uv run pytest

# Lint (check only)
uv run ruff check src/ tests/

# Lint (auto-fix)
uv run ruff check --fix src/ tests/

# Format (check only)
uv run ruff format --check src/ tests/

# Format (apply)
uv run ruff format src/ tests/
```

**Required order**: Always run `uv run pytest` and `uv run ruff check src/ tests/` before committing.

## Application Commands

Both invocation styles work, when venv is activated:

```bash
# Via installed script
terraform-registry-stub cache -m manifest.yaml -o ./cache
terraform-registry-stub serve -c ./cache -p 8080

# Via python -m (document this in examples)
python3 -m terraform_registry_stub cache -m manifest.yaml -o ./cache
python3 -m terraform_registry_stub serve -c ./cache -p 8080
```

## Project Structure

```
src/terraform_registry_stub/
├── __init__.py      # Package metadata
├── __main__.py      # Entry point for python -m invocation
├── cli.py           # argparse CLI with subcommands
├── models.py        # Pydantic v2 models for validation
├── utils.py         # Version constraint resolution
├── client.py        # httpx async HTTP client
├── cache.py         # Cache command implementation
└── serve.py         # FastAPI server implementation
```

## Important Quirks

1. **YAML gotcha**: Provider type `null` must be quoted (`type: "null"`) to prevent YAML parsing as None
2. **Module entry point**: `__main__.py` enables `python -m terraform_registry_stub` invocation
3. **Async everywhere**: Uses httpx for concurrent downloads, FastAPI for server
4. **OR logic**: Multiple `version_constraints` entries are combined with OR, not AND
5. **pytest config**: `filterwarnings` in `pyproject.toml` suppresses false-positive AsyncMock warnings

## Testing

- Test path: `tests/`
- Coverage configured in `pyproject.toml` under `[tool.pytest.ini_options]`
- pytest-asyncio used for async tests
- Run with: `uv run pytest`

## Dependencies

Core: httpx (async), FastAPI, Pydantic v2, Rich, semantic-version, PyYAML
Dev: pytest, pytest-cov, pytest-asyncio, ruff

Do not add mypy, flake8, or black—ruff handles linting and formatting.
