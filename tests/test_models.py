"""Tests for data models."""

import pytest
from datetime import datetime

from anki_vocab.models import WordEntry, StageStatus, ProcessingResult


def test_word_entry_creation():
    """Test WordEntry creation and default values."""
    entry = WordEntry(original="jabuka")
    
    assert entry.original == "jabuka"
    assert entry.canonical_form is None
    assert entry.part_of_speech is None
    assert entry.word_type is None
    assert entry.translation is None
    assert entry.definition is None
    assert entry.example_sentences is None
    assert entry.image_prompt is None
    assert entry.image_files is None


def test_word_entry_with_data():
    """Test WordEntry with all fields populated."""
    entry = WordEntry(
        original="jabuka",
        canonical_form="jabuka",
        part_of_speech="imenica",
        word_type="SIMPLE",
        translation="apple",
        definition="{{c1::Jabuka}} (imenica) je voće koje raste na stablu.",
        example_sentences=["{{c1::Jabuka}} je crvena.", "Kupio sam {{c1::jabuku}}."],
        image_prompt="A red apple on a tree",
        image_files=["image1.jpg", "image2.jpg"]
    )
    
    assert entry.original == "jabuka"
    assert entry.canonical_form == "jabuka"
    assert entry.part_of_speech == "imenica"
    assert entry.word_type == "SIMPLE"
    assert entry.translation == "apple"
    assert len(entry.example_sentences) == 2
    assert len(entry.image_files) == 2


def test_stage_status_defaults():
    """Test StageStatus default values."""
    status = StageStatus()
    
    assert status.metadata is False
    assert status.definition is False
    assert status.examples is False
    assert status.image_prompt is False
    assert status.image_generation is False
    assert status.completed_at is None


def test_stage_status_with_data():
    """Test StageStatus with data."""
    now = datetime.now()
    status = StageStatus(
        metadata=True,
        definition=True,
        examples=False,
        image_prompt=True,
        image_generation=False,
        completed_at=now
    )
    
    assert status.metadata is True
    assert status.definition is True
    assert status.examples is False
    assert status.image_prompt is True
    assert status.image_generation is False
    assert status.completed_at == now


def test_processing_result():
    """Test ProcessingResult creation."""
    word = WordEntry(original="jabuka")
    status = StageStatus(metadata=True)
    
    result = ProcessingResult(word=word, stage_status=status)
    
    assert result.word == word
    assert result.stage_status == status
    assert result.error is None


def test_processing_result_with_error():
    """Test ProcessingResult with error."""
    word = WordEntry(original="jabuka")
    status = StageStatus()
    
    result = ProcessingResult(
        word=word, 
        stage_status=status, 
        error="API rate limit exceeded"
    )
    
    assert result.word == word
    assert result.stage_status == status
    assert result.error == "API rate limit exceeded" 