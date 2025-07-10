"""Data models for the Anki vocabulary generator."""

from datetime import datetime
from typing import List, Optional
from pydantic import BaseModel


class WordEntry(BaseModel):
    """Represents a word entry with all its metadata and generated content."""
    
    original: str
    canonical_form: Optional[str] = None
    part_of_speech: Optional[str] = None  # imenica, glagol, pridjev, etc.
    word_type: Optional[str] = None  # SIMPLE | COMPLEX
    translation: Optional[str] = None
    definition: Optional[str] = None
    example_sentences: Optional[List[str]] = None
    image_prompt: Optional[str] = None
    image_files: Optional[List[str]] = None


class StageStatus(BaseModel):
    """Tracks the completion status of each processing stage."""
    
    metadata: bool = False
    definition: bool = False
    examples: bool = False
    image_prompt: bool = False
    image_generation: bool = False
    completed_at: Optional[datetime] = None


class ProcessingResult(BaseModel):
    """Result of processing a word through the pipeline."""
    
    word: WordEntry
    stage_status: StageStatus
    error: Optional[str] = None 