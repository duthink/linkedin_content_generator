"""Tests for src/output_manager.py: checking, formatting and saving content."""
import json
from pathlib import Path

import pytest
import yaml

from output_manager import (
    ContentFormatter,
    ContentValidator,
    OutputError,
    OutputManager,
    ValidationError,
)


# --- Sample content, one per content type -----------------------------------

def sample_content():
    meta = {"topic": "AI Testing"}
    return {
        "text": {"type": "text", "content": "Hello world", "metadata": meta},
        "carousel": {
            "type": "carousel",
            "hook": "Hook",
            "slides": [{"title": "Intro", "content": "Slide body"}],
            "cta": "Follow along",
            "metadata": meta,
        },
        "poll": {
            "type": "poll",
            "hook": "Question?",
            "context": "Why it matters",
            "options": ["Yes", "No"],
            "metadata": meta,
        },
        "newsletter": {
            "type": "newsletter",
            "hook": "News",
            "sections": {"Top Stories": "Story text"},
            "cta": "Subscribe",
            "metadata": meta,
        },
        "video_script": {
            "type": "video_script",
            "hook": "Video",
            "script": {"Intro": "Say hi"},
            "duration": 3,
            "metadata": meta,
        },
        "document": {
            "type": "document",
            "hook": "Doc",
            "sections": {"Summary": "Short summary"},
            "doc_type": "whitepaper",
            "metadata": meta,
        },
    }


# --- ContentValidator --------------------------------------------------------

@pytest.mark.parametrize("content_type", list(sample_content().keys()))
def test_validator_accepts_well_formed_content(content_type):
    ContentValidator().validate_content(sample_content()[content_type], content_type)


@pytest.mark.parametrize(
    "content, message",
    [
        ("not a dict", "must be a dictionary"),
        ({}, "empty"),
        ({"content": "x"}, "metadata"),
    ],
)
def test_validator_rejects_bad_basic_shape(content, message):
    with pytest.raises(ValidationError, match=message):
        ContentValidator().validate_content(content, "text")


def test_validator_rejects_unknown_content_type():
    with pytest.raises(ValidationError, match="No validator"):
        ContentValidator().validate_content({"metadata": {}}, "podcast")


@pytest.mark.parametrize(
    "content_type, content, message",
    [
        ("text", {"metadata": {}}, "missing 'content'"),
        ("text", {"metadata": {}, "content": ""}, "empty"),
        ("carousel", {"metadata": {}}, "missing 'slides'"),
        ("carousel", {"metadata": {}, "slides": "x"}, "must be a list"),
        ("poll", {"metadata": {}}, "missing 'options'"),
        ("poll", {"metadata": {}, "options": "x"}, "must be a list"),
        ("newsletter", {"metadata": {}}, "missing 'sections'"),
        ("newsletter", {"metadata": {}, "sections": []}, "must be a dictionary"),
        ("video_script", {"metadata": {}}, "missing 'script'"),
        ("video_script", {"metadata": {}, "script": {}}, "empty"),
        ("document", {"metadata": {}}, "missing 'sections'"),
        ("document", {"metadata": {}, "sections": []}, "must be a dictionary"),
    ],
)
def test_validator_rejects_missing_type_fields(content_type, content, message):
    with pytest.raises(ValidationError, match=message):
        ContentValidator().validate_content(content, content_type)


# --- ContentFormatter --------------------------------------------------------

def test_format_text():
    assert ContentFormatter().text({"content": "Hello"}) == "Hello"


def test_format_poll():
    result = ContentFormatter().poll(sample_content()["poll"])
    assert result == "# Question?\n\n## Context\n\nWhy it matters\n\n## Options\n\n- Yes\n- No"


def test_format_carousel():
    result = ContentFormatter().carousel(sample_content()["carousel"])
    assert result.startswith("# Hook\n")
    assert "## Slide 1: Intro" in result
    assert "Slide body" in result
    assert "## Call to Action\n\nFollow along" in result


def test_format_newsletter():
    result = ContentFormatter().newsletter(sample_content()["newsletter"])
    assert result.startswith("# News")
    assert "## Top Stories\n\nStory text" in result
    assert "## Call to Action\n\nSubscribe" in result


def test_format_video_script():
    result = ContentFormatter().video_script(sample_content()["video_script"])
    assert result.startswith("# Video\n\nDuration: 3 minutes")
    assert "## Intro\n\nSay hi" in result


def test_format_document():
    result = ContentFormatter().document(sample_content()["document"])
    assert result.startswith("# Doc\n\nDocument Type: whitepaper")
    assert "## Summary\n\nShort summary" in result


def test_formatter_falls_back_when_result_is_empty():
    # Empty text content produces an error page instead of an empty file.
    result = ContentFormatter().text({"content": ""})
    assert result.startswith("# Error Formatting Content")


def test_static_formatters_match_instance_formatters():
    content = sample_content()
    formatter = ContentFormatter()
    assert ContentFormatter._format_poll(content["poll"]) == formatter.poll(content["poll"])
    assert ContentFormatter._format_carousel(content["carousel"]) == formatter.carousel(content["carousel"])
    assert ContentFormatter._format_newsletter(content["newsletter"]) == formatter.newsletter(content["newsletter"])
    assert ContentFormatter._format_video_script(content["video_script"]) == formatter.video_script(content["video_script"])
    assert ContentFormatter._format_document(content["document"]) == formatter.document(content["document"])


# --- OutputManager helpers ---------------------------------------------------

@pytest.fixture
def manager(tmp_path):
    return OutputManager(base_dir=str(tmp_path / "output"))


def test_init_creates_output_folder_and_removes_tmp_files(tmp_path):
    base = tmp_path / "output"
    base.mkdir()
    leftover = base / "old.tmp"
    leftover.write_text("x")
    OutputManager(base_dir=str(base), backup_dir=str(tmp_path / "backup"))
    assert base.is_dir()
    assert (tmp_path / "backup").is_dir()
    assert not leftover.exists()


def test_formatters_cover_every_content_type(manager):
    assert set(manager.FORMATTERS) == set(sample_content())


@pytest.mark.parametrize(
    "text, expected",
    [
        ("AI Trends", "ai trends"),
        ("a/b:c?", "a_b_c_"),
        ("", "untitled"),
        (None, "untitled"),
        ("  ", "untitled"),
    ],
)
def test_sanitize_filename(manager, text, expected):
    assert manager._sanitize_filename(text) == expected


def test_checksum_ignores_metadata(manager):
    a = {"content": "x", "metadata": {"generation_time": "1"}}
    b = {"content": "x", "metadata": {"generation_time": "2"}}
    assert manager._compute_checksum(a) == manager._compute_checksum(b)
    assert manager._compute_checksum(a) != manager._compute_checksum({"content": "y"})


def test_normalize_does_not_change_the_original(manager):
    original = {"content": "x", "metadata": {}}
    manager._normalize_content(original)
    assert "metadata" in original


def test_retry_operation_retries_then_succeeds(manager, monkeypatch):
    monkeypatch.setattr("output_manager.time.sleep", lambda s: None)
    calls = []

    def flaky():
        calls.append(1)
        if len(calls) < 3:
            raise IOError("try again")
        return "ok"

    assert manager._retry_operation(flaky) == "ok"
    assert len(calls) == 3


def test_retry_operation_gives_up_after_max_retries(manager, monkeypatch):
    monkeypatch.setattr("output_manager.time.sleep", lambda s: None)

    def always_fails():
        raise IOError("nope")

    with pytest.raises(IOError):
        manager._retry_operation(always_fails)


# --- OutputManager.save_content ----------------------------------------------

@pytest.mark.parametrize("content_type", list(sample_content().keys()))
def test_save_content_writes_json_formatted_and_metadata(tmp_path, content_type):
    base = tmp_path / "output"
    manager = OutputManager(base_dir=str(base))
    content = sample_content()[content_type]

    paths = manager.save_content(content, content_type)

    assert set(paths) == {"json", "formatted", "metadata"}
    for path in paths.values():
        assert Path(path).is_file()
        # Files land in output/<date>/<content_type>/
        assert Path(path).parent.name == content_type
        assert Path(path).parent.parent.parent == base

    assert json.loads(Path(paths["json"]).read_text(encoding="utf-8")) == content
    assert yaml.safe_load(Path(paths["metadata"]).read_text(encoding="utf-8")) == content["metadata"]
    expected_ext = ".txt" if content_type == "text" else ".md"
    assert paths["formatted"].endswith(expected_ext)
    assert Path(paths["json"]).name.startswith("ai testing_")


def test_save_content_copies_files_to_backup(tmp_path):
    manager = OutputManager(base_dir=str(tmp_path / "output"), backup_dir=str(tmp_path / "backup"))
    paths = manager.save_content(sample_content()["text"], "text")
    for path in paths.values():
        relative = Path(path).relative_to(tmp_path / "output")
        assert (tmp_path / "backup" / relative).is_file()


def test_save_content_rejects_invalid_content(manager):
    with pytest.raises(OutputError, match="Content save failed"):
        manager.save_content({"content": "no metadata"}, "text")


def test_safe_save_returns_paths(tmp_path):
    manager = OutputManager(base_dir=str(tmp_path / "output"), backup_dir=str(tmp_path / "backup"))
    paths = manager.safe_save(sample_content()["poll"], "poll")
    assert Path(paths["formatted"]).is_file()


def test_safe_save_raises_on_failure(tmp_path):
    manager = OutputManager(base_dir=str(tmp_path / "output"), backup_dir=str(tmp_path / "backup"))
    with pytest.raises(OutputError):
        manager.safe_save({"metadata": {}}, "poll")
