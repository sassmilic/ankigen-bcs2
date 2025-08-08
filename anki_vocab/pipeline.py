"""Main pipeline for processing BCS words through all stages."""

import asyncio
import time
from pathlib import Path
from typing import Any, Dict, List

import structlog

from . import prompts
from .config import BATCH_SIZE, MAX_PARALLEL_REQUESTS, MODEL_NAME, TEMPERATURE
from .image_fetcher import ImageFetcher
from .models import ProcessingResult, StageStatus, WordEntry
from .openai_client import generate_response, generate_response_json
from .utils import (
    get_word_status,
    update_word_status,
)

log = structlog.get_logger()


class Pipeline:
    """Main pipeline for processing words through all stages."""
    
    def __init__(self, force: bool = False, test_mode: bool = False, temperature: float = TEMPERATURE):
        self.force = force
        self.test_mode = test_mode
        self.temperature = temperature
        self.semaphore = asyncio.Semaphore(MAX_PARALLEL_REQUESTS)
        self.image_fetcher = ImageFetcher()
    
    async def process(self, words: List[str]) -> List[ProcessingResult]:
        """Process a batch of words through the pipeline."""
        log.info("Starting batch processing", word_count=len(words))
        
        # Initialize word entries
        entries = [WordEntry(original=word) for word in words]
        
        batches = [entries[i:i + BATCH_SIZE] for i in range(0, len(entries), BATCH_SIZE)]
        
        # Process batches in parallel
        batch_tasks = [self._process_batch(batch) for batch in batches]
        batch_results = await asyncio.gather(*batch_tasks)

        # Flatten results
        results = [item for batch_result in batch_results for item in batch_result]
        
        log.info("Batch processing completed", total_words=len(results))
        return results
    
    async def _process_batch(self, entries: List[WordEntry]) -> List[ProcessingResult]:
        """Process a single batch of word entries."""
        # Stage 1: Metadata (always run)
        await self._run_stage_1_metadata(entries)
        
        # Stage 2: Definition (only for COMPLEX words)
        complex_entries = [e for e in entries if e.word_type == "COMPLEX"]
        if complex_entries:
            await self._run_stage_2_definition(complex_entries)
        
        # Stage 3: Example sentences (only for COMPLEX words)
        if complex_entries:
            await self._run_stage_3_examples(complex_entries)
        
        # Stage 4: Image prompt (only for COMPLEX words)
        if complex_entries:
            await self._run_stage_4_image_prompt(complex_entries)
        
        # Stage 5: Image generation/fetching
        await self._run_stage_5_images(entries)
        
        # Create results
        results = []
        for entry in entries:
            if self.test_mode:
                status = StageStatus()  # Empty status for test mode
            else:
                status = get_word_status(entry.canonical_form) or StageStatus()
            result = ProcessingResult(word=entry, stage_status=status)
            results.append(result)
        
        return results
    
    async def _run_stage_1_metadata(self, entries: List[WordEntry]):
        """Stage 1: Extract metadata for all words."""
        log.info("Starting Stage 1: Metadata", count=len(entries))
        
        # Check which words need processing
        words_to_process, skipped_words = self._filter_entries_for_processing(entries, "Stage 1: Metadata")
        
        if not words_to_process:
            return
        
        # Prepare batch request
        word_list = [entry.original for entry in words_to_process]
        prompt = prompts.PROMPT_WORD_METADATA.format(word_list=word_list)
        
        messages = [{"role": "user", "content": prompt}]
        
        async with self.semaphore:
            t0 = time.perf_counter()
            try:
                response = await generate_response_json(MODEL_NAME, messages)
                elapsed = 1000 * (time.perf_counter() - t0)
                log.info("Stage 1 completed", elapsed_ms=elapsed, count=len(response))
                
                # Update entries with metadata
                for item in response:
                    word = item.get("word")
                    entry = next((e for e in words_to_process if e.original == word), None)
                    if entry:
                        entry.canonical_form = item.get("canonical_form")
                        entry.part_of_speech = item.get("part_of_speech")
                        entry.word_type = item.get("word_type")
                        entry.translation = item.get("translation")
                        
                        # Update database (skip in test mode)
                        if not self.test_mode:
                            status = StageStatus(metadata=True)
                            update_word_status(entry.canonical_form, status)
                
            except Exception as e:
                log.error("Stage 1 failed", error=str(e))
                raise
    
    async def _run_stage_2_definition(self, entries: List[WordEntry]):
        """Stage 2: Generate definitions for COMPLEX words."""
        log.info("Starting Stage 2: Definitions", count=len(entries))
        
        # Check which words need processing
        words_to_process, skipped_words = self._filter_entries_for_processing(entries, "Stage 2: Definitions", "definition")
        
        if not words_to_process:
            return
        
        # Prepare batch request
        word_list = [entry.original for entry in words_to_process]
        prompt = prompts.PROMPT_WORD_DEFINITION.format(word_list=word_list)
        
        messages = [{"role": "user", "content": prompt}]
        
        async with self.semaphore:
            t0 = time.perf_counter()
            try:
                response = await generate_response_json(MODEL_NAME, messages)
                elapsed = 1000 * (time.perf_counter() - t0)
                log.info("Stage 2 completed", elapsed_ms=elapsed, count=len(response))
                
                # Update entries with definitions
                for item in response:
                    word = item.get("word")
                    entry = next((e for e in words_to_process if e.original == word), None)
                    if entry:
                        entry.definition = item.get("definition")
                        
                        # Update database (skip in test mode)
                        if not self.test_mode:
                            status = get_word_status(entry.canonical_form) or StageStatus(metadata=True)
                            status.definition = True
                            update_word_status(entry.canonical_form, status)
                
            except Exception as e:
                log.error("Stage 2 failed", error=str(e))
                raise
    
    async def _run_stage_3_examples(self, entries: List[WordEntry]):
        """Stage 3: Generate example sentences for COMPLEX words."""
        log.info("Starting Stage 3: Examples", count=len(entries))
        
        # Check which words need processing
        words_to_process, skipped_words = self._filter_entries_for_processing(entries, "Stage 3: Examples", "examples")
        
        if not words_to_process:
            return
        
        # Prepare batch request
        word_list = [entry.original for entry in words_to_process]
        prompt = prompts.PROMPT_EXAMPLE_SENTENCES.format(word_list=word_list)
        
        messages = [{"role": "user", "content": prompt}]
        
        async with self.semaphore:
            t0 = time.perf_counter()
            try:
                response = await generate_response_json(MODEL_NAME, messages)
                elapsed = 1000 * (time.perf_counter() - t0)
                log.info("Stage 3 completed", elapsed_ms=elapsed, count=len(response))
                
                # Update entries with examples
                for item in response:
                    word = item.get("word")
                    entry = next((e for e in words_to_process if e.original == word), None)
                    if entry:
                        entry.example_sentences = item.get("example_sentences", [])
                        
                        # Update database (skip in test mode)
                        if not self.test_mode:
                            status = get_word_status(entry.canonical_form) or StageStatus(metadata=True, definition=True)
                            status.examples = True
                            update_word_status(entry.canonical_form, status)
                
            except Exception as e:
                log.error("Stage 3 failed", error=str(e))
                raise
    
    async def _run_stage_4_image_prompt(self, entries: List[WordEntry]):
        """Stage 4: Generate image prompts for COMPLEX words."""
        log.info("Starting Stage 4: Image prompts", count=len(entries))
        
        # Check which words need processing
        words_to_process, skipped_words = self._filter_entries_for_processing(entries, "Stage 4: Image prompts", "image_prompt")
        
        if not words_to_process:
            return
        
        # Process each word individually (limited concurrency)
        semaphore = asyncio.Semaphore(3)  # Max 3 parallel as specified
        
        async def process_single_prompt(entry: WordEntry):
            async with semaphore:
                input_json = {
                    "word": entry.original,
                    "pos": entry.part_of_speech,
                    "definitions": [entry.definition] if entry.definition else []
                }
                
                prompt = prompts.PROMPT_IMAGE_PROMPT_GENERATOR.format(input_data=input_json)
                messages = [{"role": "user", "content": prompt}]
                
                try:
                    response = await generate_response(MODEL_NAME, messages)
                    entry.image_prompt = response.strip()
                    
                    # Log the generated image prompt
                    log.info("Image prompt generated", word=entry.original, prompt=entry.image_prompt)
                    
                    # Update database (skip in test mode)
                    if not self.test_mode:
                        status = get_word_status(entry.canonical_form) or StageStatus(metadata=True, definition=True, examples=True)
                        status.image_prompt = True
                        update_word_status(entry.canonical_form, status)
                    
                except Exception as e:
                    log.error("Image prompt generation failed", word=entry.original, error=str(e))
                    raise
        
        # Run all prompts concurrently
        tasks = [process_single_prompt(entry) for entry in words_to_process]
        await asyncio.gather(*tasks)
        
        log.info("Stage 4 completed", count=len(words_to_process))
    
    async def _run_stage_5_images(self, entries: List[WordEntry]):
        """Stage 5: Generate or fetch images for all words."""
        log.info("Starting Stage 5: Images", count=len(entries))
        
        # Check which words need processing
        words_to_process, skipped_words = self._filter_entries_for_processing(entries, "Stage 5: Images", "image_generation", require_canonical=True)
        
        if not words_to_process:
            return
        
        # Process each word individually (sequential for image generation)
        for i, entry in enumerate(words_to_process):
            
            try:
                if entry.word_type == "SIMPLE":
                    # Fetch from Pexels
                    await self.image_fetcher.fetch_pexels_images(entry)
                else:
                    # Generate with DALL-E
                    await self.image_fetcher.generate_dalle_image(entry)
                
                # Only update database if images were successfully generated/fetched
                if entry.image_files:
                    if not self.test_mode:
                        status = get_word_status(entry.canonical_form) or StageStatus()
                        status.image_generation = True
                        update_word_status(entry.canonical_form, status)
                    log.info("Image processing completed successfully", word=entry.original, image_count=len(entry.image_files))
                else:
                    log.warning("No images were generated/fetched", word=entry.original, word_type=entry.word_type)
                
                # Add delay between image generation requests to avoid rate limits
                if i < len(words_to_process) - 1:  # Don't delay after the last one
                    await asyncio.sleep(3)  # 3 second delay between requests
                
            except Exception as e:
                log.error("Image processing failed", word=entry.original, error=str(e))
                raise
        
        log.info("Stage 5 completed", count=len(entries))

    def _filter_entries_for_processing(self, entries: List[WordEntry], stage_name: str, check_field: str = None, require_canonical: bool = False) -> tuple[List[WordEntry], List[str]]:
        """Helper function to filter entries that need processing for a given stage.
        
        Args:
            entries: List of word entries to check
            stage_name: Name of the stage for logging
            check_field: Optional field name to check in status (e.g., 'definition', 'examples')
            require_canonical: Whether to skip entries without canonical_form
            
        Returns:
            Tuple of (words_to_process, skipped_words)
        """
        words_to_process = []
        skipped_words = []
        
        for entry in entries:
            # Skip entries without canonical_form if required
            if require_canonical and not entry.canonical_form:
                continue
                
            if self.test_mode:
                words_to_process.append(entry)
            else:
                if check_field:
                    # For stages that check a specific field in status
                    status = get_word_status(entry.canonical_form)
                    if self.force or not status or not getattr(status, check_field, False):
                        words_to_process.append(entry)
                    else:
                        skipped_words.append(entry.original)
                else:
                    # For stage 1 (metadata) - check if word exists at all
                    if self.force or not get_word_status(entry.original):
                        words_to_process.append(entry)
                    else:
                        skipped_words.append(entry.original)
        
        if skipped_words:
            log.info(f"{stage_name}: Skipping words already processed", words=skipped_words)
        
        if not words_to_process:
            log.info(f"{stage_name}: All words already processed")
        
        return words_to_process, skipped_words


async def process(words: List[str], force: bool = False, test_mode: bool = False, temperature: float = TEMPERATURE) -> List[ProcessingResult]:
    """Convenience function to process a batch of words."""
    pipeline = Pipeline(force=force, test_mode=test_mode, temperature=temperature)
    return await pipeline.process(words) 