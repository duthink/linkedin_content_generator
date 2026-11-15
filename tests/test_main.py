"""Tests for src/main.py: the command-line tool and its checks.

A made-up API key is used and the OpenAI call is replaced with fixed text.
"""
from pathlib import Path

import pytest
import yaml
from click.testing import CliRunner

import main
from linkedin_generator import ContentGenerator
from output_manager import OutputManager

FAKE_KEY = "test-key-not-real"


@pytest.fixture
def cli():
    return main.LinkedInContentCLI()


@pytest.fixture
def project_config(config_path):
    with open(config_path) as f:
        return yaml.safe_load(f)


@pytest.fixture(autouse=True)
def no_dotenv(monkeypatch):
    """Don't read a developer's real .env file during tests."""
    monkeypatch.setattr(main, "load_dotenv", lambda *a, **k: None)


# --- validate_env ------------------------------------------------------------

def test_validate_env_requires_api_key(cli, monkeypatch):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    with pytest.raises(ValueError, match="OPENAI_API_KEY"):
        cli.validate_env()


def test_validate_env_accepts_api_key(cli, monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", FAKE_KEY)
    cli.validate_env()


# --- validate_config ---------------------------------------------------------

def test_validate_config_accepts_project_config(cli, project_config):
    cli.validate_config(project_config)


@pytest.mark.parametrize("section", ["content_config", "brand_voice", "templates"])
def test_validate_config_requires_sections(cli, project_config, section):
    del project_config[section]
    with pytest.raises(ValueError, match=f"Missing required section: {section}"):
        cli.validate_config(project_config)


@pytest.mark.parametrize(
    "section, key",
    [
        ("content_config", "primary_goal"),
        ("content_config", "target_audience"),
        ("brand_voice", "tone"),
        ("brand_voice", "style"),
    ],
)
def test_validate_config_requires_fields(cli, project_config, section, key):
    del project_config[section][key]
    with pytest.raises(ValueError, match=f"Missing {key} in {section}"):
        cli.validate_config(project_config)


# --- validate_components -----------------------------------------------------

def test_validate_components_accepts_real_output_manager(cli, tmp_path):
    cli.validate_components(None, OutputManager(base_dir=str(tmp_path / "out")))


def test_validate_components_rejects_missing_formatters(cli):
    class PartialOutput:
        FORMATTERS = {"text": None}

    with pytest.raises(ValueError, match="Missing formatters"):
        cli.validate_components(None, PartialOutput())


# --- load_config and cleanup -------------------------------------------------

def test_load_config_reads_yaml(cli, config_path, project_config):
    assert cli.load_config(config_path) == project_config


def test_load_config_missing_file(cli, tmp_path):
    with pytest.raises(FileNotFoundError):
        cli.load_config(str(tmp_path / "missing.yaml"))


def test_load_config_bad_yaml(cli, tmp_path):
    bad = tmp_path / "bad.yaml"
    bad.write_text("a: [1, 2")
    with pytest.raises(yaml.YAMLError):
        cli.load_config(str(bad))


def test_cleanup_removes_tmp_files_only(cli, tmp_path):
    folder = tmp_path / "output" / "sub"
    folder.mkdir(parents=True)
    (folder / "half_written.tmp").write_text("x")
    (folder / "keep.md").write_text("x")
    cli.cleanup_temp_files()
    assert not (folder / "half_written.tmp").exists()
    assert (folder / "keep.md").exists()


def test_initialize_components(cli, config_path):
    generator, output_manager = cli.initialize_components(config_path, FAKE_KEY)
    assert isinstance(generator, ContentGenerator)
    assert isinstance(output_manager, OutputManager)


# --- The command itself ------------------------------------------------------

def test_command_fails_without_api_key(config_path, monkeypatch):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    result = CliRunner().invoke(
        main.main, ["--config", config_path, "--topic", "Robots", "--content-type", "text"]
    )
    assert result.exit_code == 1
    assert "OPENAI_API_KEY not found" in result.output


def test_command_rejects_unknown_content_type(config_path):
    result = CliRunner().invoke(
        main.main, ["--config", config_path, "--topic", "Robots", "--content-type", "podcast"]
    )
    assert result.exit_code == 2  # click usage error


def test_command_generates_text_post(config_path, monkeypatch, tmp_path):
    monkeypatch.setenv("OPENAI_API_KEY", FAKE_KEY)
    monkeypatch.setattr(
        ContentGenerator, "_get_completion",
        lambda self, prompt: "Fake generated text that is comfortably longer than fifty characters.",
    )
    result = CliRunner().invoke(
        main.main, ["--config", config_path, "--topic", "Robots", "--content-type", "text"]
    )
    assert result.exit_code == 0, result.output
    assert "Files generated:" in result.output
    assert "Content Preview:" in result.output
    assert "Content generated successfully!" in result.output
    assert list((tmp_path / "output").rglob("*.json"))
