# LinkedIn Content Generator

A command-line tool that writes LinkedIn content with OpenAI. You give it a topic and a content type; it writes the piece in the brand voice set in `config.yaml` and saves it to the `output/` folder.

## Table of Contents
- [What it makes](#what-it-makes)
- [Requirements](#requirements)
- [Installation](#installation)
- [Usage](#usage)
- [Output files](#output-files)
- [Configuration](#configuration)
- [Using it from Python](#using-it-from-python)
- [Logging](#logging)
- [Running the tests](#running-the-tests)
- [Project structure](#project-structure)
- [Known limitations](#known-limitations)
- [Contributing](#contributing)

## What it makes

| Content type   | What you get |
|----------------|--------------|
| `text`         | A post with a hook, main body, call to action and hashtags |
| `carousel`     | A title plus one slide per section (sections come from `templates.carousel_sections`) |
| `poll`         | A poll question, a short intro, and up to `poll_options` (4) answers taken from `templates.poll_structures` |
| `newsletter`   | A newsletter with one part per section in `templates.newsletter_sections` |
| `video_script` | A script split into the timed sections in `templates.video_script_sections` |
| `document`     | A whitepaper laid out with the sections in `templates.document_sections.whitepaper` |

The writing is done by an OpenAI model, `gpt-4.1-mini` by default (see [Choosing the model](#choosing-the-model)). Failed calls are retried up to 3 times, waiting a little longer each time.

## Requirements

- Python 3.8 or newer
- An OpenAI API key

## Installation

```bash
git clone https://github.com/duthink/linkedin_content_generator.git
cd linkedin_content_generator
pip install -r requirements.txt
```

Create a `.env` file in the project root (it is already in `.gitignore`, so it won't be committed):

```env
OPENAI_API_KEY=your_api_key_here
```

### Choosing the model

The OpenAI model is set by `model:` at the top of `config.yaml` (default `gpt-4.1-mini`). To upgrade, change that line; no code change is needed. To try a different model without editing the config, set `OPENAI_MODEL` in `.env` or your shell, which takes priority:

```env
OPENAI_MODEL=gpt-4.1
```

If neither is set, the tool falls back to `gpt-4.1-mini`. The model you pick must work with OpenAI's chat completions API and accept a `temperature` setting (the tool uses 0.7); some reasoning models don't, and their calls will fail.

## Usage

Run the tool from the project root:

```bash
python src/main.py --topic "AI in Healthcare" --content-type text
```

If you leave out `--topic` or `--content-type`, the tool asks for them.

### Options

| Option | Short | Default | Description |
|--------|-------|---------|-------------|
| `--config` | `-c` | `config.yaml` | Path to the configuration file |
| `--topic` | `-t` | asked for | Topic to write about |
| `--content-type` | `-ct` | asked for | One of `text`, `carousel`, `poll`, `newsletter`, `video_script`, `document` |
| `--slides` | `-s` | `carousel_slides` in the config (6) | Number of slides for a carousel (see [Known limitations](#known-limitations)) |
| `--duration` | `-d` | `video_length_minutes` in the config (3) | Video script length, in **minutes** |
| `--backup-dir` | `-b` | none | Also copy the saved files into this folder |

### Examples

```bash
# Text post
python src/main.py -t "AI in Healthcare" -ct text

# Poll
python src/main.py -t "AI in Healthcare" -ct poll

# Newsletter
python src/main.py -t "AI in Healthcare" -ct newsletter

# 2-minute video script
python src/main.py -t "AI in Healthcare" -ct video_script --duration 2

# Whitepaper, with a backup copy of the files
python src/main.py -t "AI in Healthcare" -ct document --backup-dir backups
```

When it finishes, the tool prints where the files were saved and a preview of the first 500 characters.

## Output files

Each run saves three files to `output/<content_type>/`, named after the topic and the time of the run:

```
output/text/
├── ai in healthcare_20261116_091500.json        # Everything that was generated
├── ai in healthcare_20261116_091500.txt         # Ready-to-post text (.md for other types)
└── ai in healthcare_20261116_091500_meta.yaml   # Topic, hook, CTA, time created and config used
```

If `--backup-dir` is given, the same files are also copied there. The `output/` folder is in `.gitignore`.

## Configuration

Everything that shapes the writing lives in `config.yaml`:

| Section | What it controls |
|---------|------------------|
| `content_types`, `content_goals`, `optimization_metrics` | The lists of supported types, goals and metrics |
| `brand_voice` | Tone, style, personality, key phrases, emoji style and hashtags |
| `content_config` | Main goal, target audience, industry and extra settings (`carousel_slides`, `poll_options`, `video_length_minutes`, …) |
| `templates` | Hook and call-to-action lines for each type, plus the sections used for carousels, newsletters, video scripts and documents. `{topic}` is replaced with your topic |
| `formatting` | Layout guidance for each content type |
| `engagement_patterns` | Patterns that tend to perform well |

The tool stops with an error if any of these are missing or empty: `content_config.primary_goal`, `content_config.target_audience`, `content_config.industry_context`, `brand_voice.tone`, `brand_voice.style`, or the `templates` section.

Example brand voice:

```yaml
brand_voice:
  tone:
    - casual
    - empathetic
  style:
    - conversational
    - storytelling
  personality:
    - authentic
    - curious
  emoji_style: minimal
  industry_hashtags:
    - AIJourney
    - TechLessons
```

## Using it from Python

The modules import each other by name, so put `src/` on the import path first (for example `export PYTHONPATH=src`).

```python
from linkedin_generator import ContentGenerator
from output_manager import OutputError

generator = ContentGenerator(api_key="your_api_key", config_path="config.yaml")

try:
    content = generator.generate(content_type="carousel", topic="AI in Healthcare", num_slides=5)
except OutputError as e:
    print(f"Could not save the content: {e}")

print(content["output_paths"])  # {'json': ..., 'formatted': ..., 'metadata': ...}
```

`generate()` saves the files itself and returns the generated content with an `output_paths` entry. Extra settings you can pass:

- `num_slides` for `carousel`
- `duration` (minutes) for `video_script`
- `document_type="case_study"` for `document` (the default is `whitepaper`)

An unknown content type raises `ValueError`. Problems saving files raise `OutputError` (from `output_manager`), which covers `FileError`, `SerializationError`, `ValidationError` and `RateLimitError`.

## Logging

Logs are written to `logs/` (also in `.gitignore`), one file per day for each level:

```
logs/
├── info/info_YYYY-MM-DD.log     # kept 30 days
├── error/error_YYYY-MM-DD.log   # kept 30 days, includes tracebacks
└── debug/debug_YYYY-MM-DD.log   # kept 15 days
```

Info and error messages are also shown in the terminal.

## Running the tests

The tests use a made-up API key and a fake stand-in for OpenAI, so they need no real key and no network.

```bash
pip install -r requirements-dev.txt
pytest
```

## Project structure

```
.
├── src/
│   ├── main.py                 # Command-line tool
│   ├── linkedin_generator.py   # Writes the content with OpenAI
│   ├── output_manager.py       # Checks, formats and saves content
│   ├── log_config.py           # Logging setup
│   └── utilities.py            # Helpers for turning config into JSON
├── tests/                      # Automated tests (pytest)
├── config.yaml                 # Brand voice, templates and settings
├── requirements.txt            # Libraries the tool needs
├── requirements-dev.txt        # Extra libraries for running the tests
├── JOURNAL.md                  # Plain-language log of changes
└── readme.md                   # This file
```

`output/` and `logs/` are created automatically the first time the tool runs.

## Known limitations

- `--slides` on the command line is currently read as text rather than a number, so carousel generation fails when it is used. Leave it out to use `carousel_slides` from `config.yaml`, or pass `num_slides` from Python.
- Documents made from the command line are always whitepapers; case studies are only available from Python.

## Contributing

Every change goes through a pull request, needs passing tests, and adds an entry to `JOURNAL.md`. See `AGENTS.md` for the full rules.
