import argparse
import warnings
from unittest.mock import patch

import pytest
import yaml

from terraform_registry_stub.cli import cmd_cache, cmd_serve, load_manifest, main
from terraform_registry_stub.models import Manifest


class TestLoadManifest:
    def test_load_manifest_success(self, tmp_path, sample_manifest_dict):
        manifest_path = tmp_path / "manifest.yaml"
        with open(manifest_path, "w") as f:
            yaml.dump(sample_manifest_dict, f)

        manifest = load_manifest(manifest_path)
        assert isinstance(manifest, Manifest)
        assert manifest.registry == "registry.terraform.io"

    def test_load_manifest_file_not_found(self, tmp_path, capsys):
        manifest_path = tmp_path / "nonexistent.yaml"

        with pytest.raises(SystemExit) as exc_info:
            load_manifest(manifest_path)

        assert exc_info.value.code == 1
        captured = capsys.readouterr()
        assert "not found" in captured.out

    def test_load_manifest_invalid_yaml(self, tmp_path, capsys):
        manifest_path = tmp_path / "invalid.yaml"
        manifest_path.write_text("invalid: yaml: content: [")

        with pytest.raises(SystemExit) as exc_info:
            load_manifest(manifest_path)

        assert exc_info.value.code == 1

    def test_load_manifest_validation_error(self, tmp_path, capsys):
        manifest_path = tmp_path / "invalid_manifest.yaml"
        with open(manifest_path, "w") as f:
            yaml.dump({"registry": "test", "providers": []}, f)

        manifest = load_manifest(manifest_path)
        assert isinstance(manifest, Manifest)


class TestCmdCache:
    def test_cmd_cache_basic(self, tmp_path, sample_manifest_dict):
        manifest_path = tmp_path / "manifest.yaml"
        with open(manifest_path, "w") as f:
            yaml.dump(sample_manifest_dict, f)

        output_dir = tmp_path / "cache"
        args = argparse.Namespace(
            manifest=manifest_path,
            output=output_dir,
            no_packages=False,
            parallel=4,
            force=False,
        )

        with patch("terraform_registry_stub.cli.cache_providers"):
            with patch("asyncio.run") as mock_run:
                cmd_cache(args)
                assert mock_run.called

    def test_cmd_cache_no_packages_flag(self, tmp_path, sample_manifest_dict):
        manifest_path = tmp_path / "manifest.yaml"
        with open(manifest_path, "w") as f:
            yaml.dump(sample_manifest_dict, f)

        args = argparse.Namespace(
            manifest=manifest_path,
            output=tmp_path / "cache",
            no_packages=True,
            parallel=4,
            force=False,
        )

        with patch("terraform_registry_stub.cli.cache_providers"):
            with patch("asyncio.run") as mock_run:
                cmd_cache(args)
                assert mock_run.called

    def test_cmd_cache_force_flag(self, tmp_path, sample_manifest_dict):
        # Use warnings context manager to suppress false positive RuntimeWarnings
        # that occur when yaml.dump() interacts with pytest-asyncio's mock patching
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", RuntimeWarning)

            manifest_path = tmp_path / "manifest.yaml"
            with open(manifest_path, "w") as f:
                yaml.dump(sample_manifest_dict, f)

            args = argparse.Namespace(
                manifest=manifest_path,
                output=tmp_path / "cache",
                no_packages=False,
                parallel=4,
                force=True,
            )

            with patch("asyncio.run"):
                with patch("terraform_registry_stub.cli.cache_providers"):
                    cmd_cache(args)


class TestCmdServe:
    def test_cmd_serve_basic(self, tmp_path):
        cache_dir = tmp_path / "cache"
        cache_dir.mkdir()

        args = argparse.Namespace(
            cache=cache_dir,
            host="127.0.0.1",
            port=8080,
            reload=False,
        )

        with patch("terraform_registry_stub.cli.run_server") as mock_server:
            cmd_serve(args)
            mock_server.assert_called_once()
            call_args = mock_server.call_args[1]
            assert call_args["host"] == "127.0.0.1"
            assert call_args["port"] == 8080
            assert call_args["reload"] is False

    def test_cmd_serve_custom_host_port(self, tmp_path):
        cache_dir = tmp_path / "cache"
        cache_dir.mkdir()

        args = argparse.Namespace(
            cache=cache_dir,
            host="0.0.0.0",
            port=9090,
            reload=False,
        )

        with patch("terraform_registry_stub.cli.run_server") as mock_server:
            cmd_serve(args)
            call_args = mock_server.call_args[1]
            assert call_args["host"] == "0.0.0.0"
            assert call_args["port"] == 9090

    def test_cmd_serve_reload_enabled(self, tmp_path):
        cache_dir = tmp_path / "cache"
        cache_dir.mkdir()

        args = argparse.Namespace(
            cache=cache_dir,
            host="127.0.0.1",
            port=8080,
            reload=True,
        )

        with patch("terraform_registry_stub.cli.run_server") as mock_server:
            cmd_serve(args)
            call_args = mock_server.call_args[1]
            assert call_args["reload"] is True

    def test_cmd_serve_nonexistent_cache_dir(self, tmp_path, capsys):
        cache_dir = tmp_path / "nonexistent"

        args = argparse.Namespace(
            cache=cache_dir,
            host="127.0.0.1",
            port=8080,
            reload=False,
        )

        with pytest.raises(SystemExit) as exc_info:
            cmd_serve(args)

        assert exc_info.value.code == 1
        captured = capsys.readouterr()
        assert "does not exist" in captured.out


class TestMain:
    def test_main_no_command(self, capsys):
        with patch("sys.argv", ["terraform-registry-stub"]), pytest.raises(SystemExit):
            main()

    def test_main_help(self):
        with patch("sys.argv", ["terraform-registry-stub", "--help"]):
            with pytest.raises(SystemExit) as exc_info:
                main()
            assert exc_info.value.code == 0

    def test_main_version(self):
        with patch("sys.argv", ["terraform-registry-stub", "--version"]):
            with pytest.raises(SystemExit) as exc_info:
                main()
            assert exc_info.value.code == 0

    def test_main_cache_command(self, tmp_path, sample_manifest_dict):
        manifest_path = tmp_path / "manifest.yaml"
        with open(manifest_path, "w") as f:
            yaml.dump(sample_manifest_dict, f)

        with patch("sys.argv", ["terraform-registry-stub", "cache", "-m", str(manifest_path)]):
            with patch("terraform_registry_stub.cli.cache_providers"):
                with patch("asyncio.run"):
                    main()

    def test_main_cache_help(self):
        with patch("sys.argv", ["terraform-registry-stub", "cache", "--help"]):
            with pytest.raises(SystemExit) as exc_info:
                main()
            assert exc_info.value.code == 0

    def test_main_serve_command(self, tmp_path):
        cache_dir = tmp_path / "cache"
        cache_dir.mkdir()

        with patch("sys.argv", ["terraform-registry-stub", "serve", "-c", str(cache_dir)]):
            with patch("terraform_registry_stub.cli.run_server"):
                main()

    def test_main_serve_help(self):
        with patch("sys.argv", ["terraform-registry-stub", "serve", "--help"]):
            with pytest.raises(SystemExit) as exc_info:
                main()
            assert exc_info.value.code == 0

    def test_main_cache_with_options(self, tmp_path, sample_manifest_dict):
        manifest_path = tmp_path / "manifest.yaml"
        with open(manifest_path, "w") as f:
            yaml.dump(sample_manifest_dict, f)

        output_dir = tmp_path / "output"

        with (
            patch(
                "sys.argv",
                [
                    "terraform-registry-stub",
                    "cache",
                    "-m",
                    str(manifest_path),
                    "-o",
                    str(output_dir),
                    "--no-packages",
                    "--parallel",
                    "8",
                    "--force",
                ],
            ),
            patch("terraform_registry_stub.cli.cache_providers"),
            patch("asyncio.run"),
        ):
            main()

    def test_main_serve_with_options(self, tmp_path):
        cache_dir = tmp_path / "cache"
        cache_dir.mkdir()

        with (
            patch(
                "sys.argv",
                [
                    "terraform-registry-stub",
                    "serve",
                    "-c",
                    str(cache_dir),
                    "--host",
                    "0.0.0.0",
                    "-p",
                    "9090",
                    "--reload",
                ],
            ),
            patch("terraform_registry_stub.cli.run_server"),
        ):
            main()
