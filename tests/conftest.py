"""Shared test setup.

The app's modules import each other by bare name (``from log_config import ...``),
so ``src/`` is put on the import path here, the same way CI does with PYTHONPATH.

Every test runs inside its own throwaway folder, so the ``logs/`` and ``output/``
folders the app creates never land in the repository.
"""
import os
import sys
import tempfile
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
SRC_DIR = REPO_ROOT / "src"
CONFIG_PATH = REPO_ROOT / "config.yaml"

if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

# Importing linkedin_generator creates a logs/ folder in the current folder
# (ContentConfig sets up logging when the class is defined). Import it once
# from a throwaway folder so that folder isn't created in the repository.
_previous_dir = os.getcwd()
os.chdir(tempfile.mkdtemp(prefix="lcg-import-"))
try:
    import linkedin_generator  # noqa: E402,F401
finally:
    os.chdir(_previous_dir)


@pytest.fixture(autouse=True)
def run_in_tmp_dir(tmp_path, monkeypatch):
    """Run each test from an empty temporary folder."""
    monkeypatch.chdir(tmp_path)
    yield tmp_path


@pytest.fixture(autouse=True)
def reset_loguru():
    """Drop any log handlers a test added so later tests start clean."""
    from loguru import logger

    yield
    logger.remove()


@pytest.fixture
def config_path():
    """Path to the real project config.yaml."""
    return str(CONFIG_PATH)
