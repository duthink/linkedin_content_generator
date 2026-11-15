"""Tests for src/linkedin_generator.py.

No real OpenAI calls are made: the call to OpenAI is replaced with a fake that
returns fixed text, and a made-up API key is used.
"""
import json
from pathlib import Path
from types import SimpleNamespace

import pytest
import yaml

import linkedin_generator
from linkedin_generator import (
    BrandVoice,
    ContentConfig,
    ContentGenerator,
    ContentGoal,
    ContentType,
)

FAKE_KEY = "test-key-not-real"
FAKE_TEXT = "Fake generated text that is comfortably longer than fifty characters."


@pytest.fixture
def fake_completion(monkeypatch):
    """Replace the OpenAI call with one that records prompts and returns fixed text."""
    prompts = []

    def fake(self, prompt):
        prompts.append(prompt)
        return FAKE_TEXT

    monkeypatch.setattr(ContentGenerator, "_get_completion", fake)
    return prompts


@pytest.fixture
def generator(config_path, fake_completion):
    return ContentGenerator(api_key=FAKE_KEY, config_path=config_path)


# --- ContentConfig -----------------------------------------------------------

def test_config_loads_from_project_yaml(config_path):
    config = ContentConfig.from_yaml(config_path)
    assert config.primary_goal is ContentGoal.THOUGHT_LEADERSHIP
    assert "startup founders" in config.target_audience
    assert config.industry_context == "AI and Machine Learning"
    assert config.brand_voice.tone[0] == "casual"
    assert config.brand_voice.emoji_style == "minimal"
    assert config.custom_parameters["carousel_slides"] == 6
    config.validate()  # the shipped config is valid


def test_config_rejects_unknown_goal(tmp_path):
    path = tmp_path / "bad.yaml"
    path.write_text(yaml.safe_dump({"content_config": {"primary_goal": "fame"}}))
    with pytest.raises(ValueError):
        ContentConfig.from_yaml(str(path))


def make_config(**overrides):
    values = dict(
        primary_goal=ContentGoal.ENGAGEMENT,
        target_audience=["devs"],
        brand_voice=BrandVoice(),
        industry_context="Software",
    )
    values.update(overrides)
    return ContentConfig(**values)


def test_brand_voice_defaults():
    voice = BrandVoice()
    assert voice.tone == ["professional"]
    assert voice.style == ["conversational"]
    assert voice.personality == ["authentic"]
    assert voice.key_phrases == []
    assert voice.industry_hashtags == []


@pytest.mark.parametrize(
    "overrides, message",
    [
        ({"target_audience": []}, "Target audience"),
        ({"industry_context": ""}, "Industry context"),
        ({"brand_voice": BrandVoice(tone=[])}, "tone"),
    ],
)
def test_config_validate_rejects_missing_values(overrides, message):
    with pytest.raises(ValueError, match=message):
        make_config(**overrides).validate()


# --- ContentGenerator setup --------------------------------------------------

def test_generator_loads_config_and_templates(generator):
    assert generator.api_key == FAKE_KEY
    assert generator.config.primary_goal is ContentGoal.THOUGHT_LEADERSHIP
    assert "hooks" in generator.templates
    assert "carousel_sections" in generator.templates


def test_generator_fails_on_missing_config(tmp_path):
    with pytest.raises(FileNotFoundError):
        ContentGenerator(api_key=FAKE_KEY, config_path=str(tmp_path / "missing.yaml"))


# --- Small building blocks ---------------------------------------------------

def test_hook_comes_from_template_and_mentions_topic(generator, fake_completion):
    hook = generator._generate_hook("Robots", ContentType.TEXT)
    templates = [t.format(topic="Robots") for t in generator.templates["hooks"]["text"]]
    assert hook in templates
    assert fake_completion == []  # no AI call needed


def test_hook_asks_ai_when_no_template(generator, fake_completion):
    generator.templates = {}
    assert generator._generate_hook("Robots", ContentType.TEXT) == FAKE_TEXT
    assert "Robots" in fake_completion[0]


def test_cta_comes_from_goal_templates(generator):
    cta = generator._generate_cta("Robots")
    goal = generator.config.primary_goal.value
    assert cta in [t.format(topic="Robots") for t in generator.templates["cta"][goal]]


def test_hashtags_come_from_brand_voice(generator):
    hashtags = generator._generate_hashtags(3)
    allowed = {f"#{t}" for t in generator.config.brand_voice.industry_hashtags}
    assert len(hashtags) == 3
    assert set(hashtags) <= allowed
    # Asking for more than exist returns all of them.
    assert set(generator._generate_hashtags(100)) == allowed


def test_format_post_without_hashtags(generator):
    post = generator._format_post(" Hook ", "line1\n\n  \nline2", " CTA ", num_hashtags=0)
    assert post == "Hook\n\nline1\n\nline2\n\nCTA"


def test_format_post_with_custom_formatting(generator):
    post = generator._format_post(
        "Hook", "line1\nline2", "CTA",
        num_hashtags=0,
        custom_formatting={"line_breaks": 1, "emoji_prefix": ">>"},
    )
    assert post == "Hook\n>> line1\n>> line2\nCTA"


def test_format_post_adds_hashtags_on_their_own_line(generator):
    post = generator._format_post("Hook", "Body", "CTA", num_hashtags=2)
    body, tags = post.rsplit("\n\n", 1)
    assert body == "Hook\n\nBody\n\nCTA"
    assert len(tags.split(" ")) == 2
    assert all(tag.startswith("#") for tag in tags.split(" "))


def test_metadata_contains_topic_and_config(generator):
    metadata = generator._generate_metadata("Robots", "Hook", "CTA")
    assert metadata["topic"] == "Robots"
    assert metadata["hook"] == "Hook"
    assert metadata["cta"] == "CTA"
    assert "generation_time" in metadata
    assert metadata["config"]["primary_goal"] == "thought_leadership"
    json.dumps(metadata)  # must be plain JSON data


@pytest.mark.parametrize(
    "prompt_type, params",
    [
        ("hook", {"topic": "Robots", "content_type": "text"}),
        ("main_content", {"topic": "Robots", "hook": "Hi"}),
        ("cta", {"topic": "Robots"}),
        ("slide", {"topic": "Robots", "section": "Intro"}),
        ("poll_context", {"topic": "Robots"}),
        ("newsletter_section", {"topic": "Robots", "section": "News"}),
        ("video_section", {"topic": "Robots", "section": "Intro", "duration": 3}),
        ("document_section", {"topic": "Robots", "section": "Intro", "doc_type": "whitepaper"}),
    ],
)
def test_create_prompt_includes_topic(generator, prompt_type, params):
    assert "Robots" in generator._create_prompt(prompt_type, params)


def test_create_prompt_rejects_unknown_type(generator):
    with pytest.raises(ValueError, match="Unknown prompt type"):
        generator._create_prompt("limerick", {"topic": "Robots"})


def test_create_prompt_needs_all_parameters(generator):
    with pytest.raises(KeyError):
        generator._create_prompt("slide", {"topic": "Robots"})


# --- The OpenAI call (faked) -------------------------------------------------

def fake_openai(monkeypatch, create):
    class FakeClient:
        def __init__(self, api_key):
            assert api_key == FAKE_KEY
            self.chat = SimpleNamespace(completions=SimpleNamespace(create=create))

    monkeypatch.setattr(linkedin_generator.openai, "OpenAI", FakeClient)
    monkeypatch.setattr(linkedin_generator, "sleep", lambda s: None)


def reply(text):
    return SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(content=text))])


def test_get_completion_returns_trimmed_text(config_path, monkeypatch):
    calls = []

    def create(**kwargs):
        calls.append(kwargs)
        return reply("  answer  ")

    fake_openai(monkeypatch, create)
    generator = ContentGenerator(api_key=FAKE_KEY, config_path=config_path)
    assert generator._get_completion("question") == "answer"
    assert calls[0]["messages"][-1] == {"role": "user", "content": "question"}


def test_get_completion_retries_then_gives_up(config_path, monkeypatch):
    attempts = []

    def create(**kwargs):
        attempts.append(1)
        raise RuntimeError("service down")

    fake_openai(monkeypatch, create)
    generator = ContentGenerator(api_key=FAKE_KEY, config_path=config_path)
    with pytest.raises(RuntimeError, match="service down"):
        generator._get_completion("question")
    assert len(attempts) == 3


# --- generate(): full runs with the fake AI ----------------------------------

def assert_saved(result, content_type):
    paths = result["output_paths"]
    assert set(paths) == {"json", "formatted", "metadata"}
    for path in paths.values():
        assert Path(path).is_file()
        assert Path(path).parent.name == content_type


def test_generate_text(generator):
    result = generator.generate("text", "Robots")
    assert result["type"] == "text"
    assert FAKE_TEXT in result["content"]
    assert result["raw_components"]["main_content"] == FAKE_TEXT
    assert result["metadata"]["topic"] == "Robots"
    assert_saved(result, "text")


def test_generate_carousel_uses_configured_slide_count(generator):
    result = generator.generate(ContentType.CAROUSEL, "Robots")
    assert len(result["slides"]) == 6  # carousel_slides in config.yaml
    assert result["slides"][0]["title"] == generator.templates["carousel_sections"][0]
    assert_saved(result, "carousel")


def test_generate_carousel_with_custom_slide_count(generator):
    result = generator.generate("carousel", "Robots", num_slides=2)
    assert len(result["slides"]) == 2


def test_generate_poll(generator):
    result = generator.generate("poll", "Robots")
    assert result["options"] == generator.templates["poll_structures"]["implementation"][:4]
    assert result["context"] == FAKE_TEXT
    assert_saved(result, "poll")


def test_generate_poll_fills_in_choices(generator):
    result = generator.generate("poll", "Robots", poll_type="preference", num_options=2)
    assert result["options"] == ["Option A: Robots Solution A", "Option B: Robots Solution B"]


def test_generate_newsletter(generator):
    result = generator.generate("newsletter", "Robots")
    assert list(result["sections"]) == generator.templates["newsletter_sections"]
    assert_saved(result, "newsletter")


def test_generate_video_script(generator):
    result = generator.generate("video_script", "Robots")
    assert result["duration"] == 3  # video_length_minutes in config.yaml
    assert list(result["script"]) == generator.templates["video_script_sections"]
    assert_saved(result, "video_script")


def test_generate_document(generator):
    result = generator.generate("document", "Robots", document_type="case_study")
    assert result["doc_type"] == "case_study"
    assert list(result["sections"]) == generator.templates["document_sections"]["case_study"]
    assert_saved(result, "document")


def test_generate_rejects_unknown_type(generator):
    with pytest.raises(ValueError):
        generator.generate("podcast", "Robots")
