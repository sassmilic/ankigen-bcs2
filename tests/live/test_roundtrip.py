"""Live tests for end-to-end processing."""

import pytest
import asyncio
from pathlib import Path

from anki_vocab.pipeline import process_batch
from anki_vocab.models import WordEntry
from tests.conftest import my_vcr, cassette, live_guard


def run_word_test(vcr_obj, word: str, cassette_name: str, expected_type: str, 
                  expected_pos: str = None, description: str = "") -> WordEntry:
    """Helper function to run a word processing test."""
    live_guard()
    
    entry = WordEntry(original=word)
    
    with vcr_obj.use_cassette(cassette(cassette_name)):
        results = asyncio.run(process_batch([entry.original], test_mode=True))
    
    processed_word = results[0].word if results else None
    assert processed_word is not None
    
    print(f"\n=== MANUAL CHECK - {description.upper()} ========================")
    print(f"canonical   : {processed_word.canonical_form}")
    print(f"translation : {processed_word.translation}")
    print(f"word type   : {processed_word.word_type}")
    print(f"part of speech: {processed_word.part_of_speech}")
    
    # Show definition and examples for COMPLEX words
    if processed_word.word_type == "COMPLEX":
        if processed_word.definition:
            print(f"definition  : {processed_word.definition}")
        if processed_word.example_sentences:
            print("examples    :")
            for i, sentence in enumerate(processed_word.example_sentences, 1):
                print(f"            {i}. {sentence}")
    
    # Log image generation details for debugging
    if processed_word.image_prompt:
        print(f"IMAGE PROMPT: {processed_word.image_prompt}")
        print(f"IMAGE MODEL: gpt-image-1 (DALL-E 3 via OpenAI)")
    else:
        print("IMAGE SOURCE: Pexels (stock photos)")
    
    if processed_word.image_files:
        print(f"image file  : {processed_word.image_files[0]}")
        print(f"Open the image; confirm it depicts {description} correctly.")
    else:
        print("image file  : NONE")
    
    # Human-in-the-loop verification
    response = input("Type Y to accept, anything else to fail: ").strip().lower()
    assert response in ["y", ""], f"Manual verification failed for {word}"
    
    return processed_word


def assert_simple_word(word: WordEntry):
    """Assert that a word was processed as SIMPLE."""
    assert word.word_type == "SIMPLE"
    assert word.canonical_form is not None
    assert word.translation is not None
    assert word.definition is None  # Should be skipped
    assert word.example_sentences is None  # Should be skipped
    assert word.image_files is not None  # Should have Pexels images


def assert_complex_word(word: WordEntry, expected_pos: str = None):
    """Assert that a word was processed as COMPLEX."""
    assert word.word_type == "COMPLEX"
    assert word.canonical_form is not None
    assert word.translation is not None
    assert word.definition is not None  # Should have definition
    assert word.example_sentences is not None  # Should have examples
    assert word.image_prompt is not None  # Should have image prompt
    assert word.image_files is not None  # Should have DALL-E image
    
    if expected_pos:
        assert word.part_of_speech in [expected_pos, expected_pos.lower(), expected_pos.title()]


@pytest.mark.live_llm
def test_roundtrip_live(my_vcr):
    """Live test for complete word processing pipeline."""
    processed_word = run_word_test(my_vcr, "jabuka", "roundtrip", "SIMPLE", description="apple")
    assert_simple_word(processed_word)


@pytest.mark.live_llm
def test_simple_word_processing(my_vcr):
    """Test processing of a SIMPLE word (should skip definition/examples)."""
    processed_word = run_word_test(my_vcr, "kuća", "simple_word", "SIMPLE", description="house")
    assert_simple_word(processed_word)


@pytest.mark.live_llm
def test_complex_word_processing(my_vcr):
    """Test processing of a COMPLEX word (should have full pipeline)."""
    processed_word = run_word_test(my_vcr, "ljubav", "complex_word", "COMPLEX", description="love")
    assert_complex_word(processed_word)


@pytest.mark.live_llm
def test_verb_processing(my_vcr):
    """Test processing of a verb (should be COMPLEX with action-based examples)."""
    processed_word = run_word_test(my_vcr, "misliti", "verb_word", "COMPLEX", "glagol", "thinking/mental activity")
    assert_complex_word(processed_word, "glagol")


@pytest.mark.live_llm
def test_abstract_concept_processing(my_vcr):
    """Test processing of an abstract concept (should be COMPLEX)."""
    processed_word = run_word_test(my_vcr, "sloboda", "abstract_word", "COMPLEX", description="freedom/liberty concept")
    assert_complex_word(processed_word)


@pytest.mark.live_llm
def test_adjective_processing(my_vcr):
    """Test processing of an adjective (should be COMPLEX with descriptive examples)."""
    processed_word = run_word_test(my_vcr, "vrijedan", "adjective_word", "COMPLEX", "pridjev", "valuable/worthy concept")
    assert_complex_word(processed_word, "pridjev") 