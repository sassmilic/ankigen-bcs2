"""Pytest configuration and fixtures."""

import hashlib
import os
import pathlib
import pytest
import vcr

# Calculate hash of prompts.py for cassette invalidation
PROMPTS_HASH = hashlib.sha256(
    pathlib.Path("anki_vocab/prompts.py").read_bytes()
).hexdigest()[:8]


def cassette(name: str) -> str:
    """Generate cassette filename with prompt hash."""
    return f"fixtures/{name}_{PROMPTS_HASH}.yaml"


@pytest.fixture
def my_vcr():
    """VCR fixture for recording/replaying HTTP interactions."""
    return vcr.VCR(
        cassette_library_dir="tests/fixtures",
        filter_headers=[("authorization", "DUMMY")],
        record_mode="once",
    )


def live_guard():
    """Check if live testing is enabled."""
    if not os.getenv("ANKI_VOCAB_LIVE"):
        pytest.skip("Live LLM disabled (set ANKI_VOCAB_LIVE=1)")


@pytest.fixture
def sample_words():
    """Sample BCS words for testing."""
    return ["jabuka", "kuća", "ljubav", "misliti"]


@pytest.fixture
def temp_data_dir(tmp_path):
    """Create temporary data directory."""
    data_dir = tmp_path / "data"
    data_dir.mkdir()
    return data_dir 