"""Main pipeline for processing BCS words through all stages."""

import asyncio
import time
from typing import List, Dict, Any
import structlog

from .config import MODEL_NAME, BATCH_SIZE, MAX_PARALLEL_REQUESTS, TEMPERATURE
from .models import WordEntry, StageStatus, ProcessingResult
from .openai_client import call_chat_json, call_chat, generate_image
from .pexels_client import search_pexels_images
from .utils import (
    get_word_status, update_word_status, download_image,
    generate_image_filename
)
from . import prompts

log = structlog.get_logger()


class Pipeline:
    """Main pipeline for processing words through all stages."""
    
    def __init__(self, force: bool = False, test_mode: bool = False, temperature: float = TEMPERATURE):
        self.force = force
        self.test_mode = test_mode
        self.temperature = temperature
        self.semaphore = asyncio.Semaphore(MAX_PARALLEL_REQUESTS)
    
    async def process_batch(self, words: List[str]) -> List[ProcessingResult]:
        """Process a batch of words through the pipeline."""
        log.info("Starting batch processing", word_count=len(words))
        
        # Initialize word entries
        entries = [WordEntry(original=word) for word in words]
        
        # Process in batches
        results = []
        for i in range(0, len(entries), BATCH_SIZE):
            batch = entries[i:i + BATCH_SIZE]
            batch_results = await self._process_batch(batch)
            results.extend(batch_results)
        
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
        words_to_process = []
        for entry in entries:
            if self.test_mode or self.force or not get_word_status(entry.original):
                words_to_process.append(entry)
        
        if not words_to_process:
            log.info("Stage 1: All words already processed")
            return
        
        # Prepare batch request
        word_list = [entry.original for entry in words_to_process]
        prompt = prompts.PROMPT_WORD_METADATA.format(word_list=word_list)
        
        messages = [{"role": "user", "content": prompt}]
        
        async with self.semaphore:
            t0 = time.perf_counter()
            try:
                response = await call_chat_json(MODEL_NAME, messages)
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
        words_to_process = []
        for entry in entries:
            if self.test_mode:
                words_to_process.append(entry)
            else:
                status = get_word_status(entry.canonical_form)
                if self.force or not status or not status.definition:
                    words_to_process.append(entry)
        
        if not words_to_process:
            log.info("Stage 2: All words already processed")
            return
        
        # Prepare batch request
        word_list = [entry.original for entry in words_to_process]
        prompt = prompts.PROMPT_WORD_DEFINITION.format(word_list=word_list)
        
        messages = [{"role": "user", "content": prompt}]
        
        async with self.semaphore:
            t0 = time.perf_counter()
            try:
                response = await call_chat_json(MODEL_NAME, messages)
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
        words_to_process = []
        for entry in entries:
            if self.test_mode:
                words_to_process.append(entry)
            else:
                status = get_word_status(entry.canonical_form)
                if self.force or not status or not status.examples:
                    words_to_process.append(entry)
        
        if not words_to_process:
            log.info("Stage 3: All words already processed")
            return
        
        # Prepare batch request
        word_list = [entry.original for entry in words_to_process]
        prompt = prompts.PROMPT_EXAMPLE_SENTENCES.format(word_list=word_list)
        
        messages = [{"role": "user", "content": prompt}]
        
        async with self.semaphore:
            t0 = time.perf_counter()
            try:
                response = await call_chat_json(MODEL_NAME, messages)
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
        words_to_process = []
        for entry in entries:
            if self.test_mode:
                words_to_process.append(entry)
            else:
                status = get_word_status(entry.canonical_form)
                if self.force or not status or not status.image_prompt:
                    words_to_process.append(entry)
        
        if not words_to_process:
            log.info("Stage 4: All words already processed")
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
                    response = await call_chat(MODEL_NAME, messages)
                    entry.image_prompt = response.strip()
                    
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
        
        # Process each word individually (sequential for image generation)
        for entry in entries:
            if not entry.canonical_form:
                continue
                
            if not self.test_mode:
                status = get_word_status(entry.canonical_form)
                if not self.force and status and status.image_generation:
                    continue
            
            try:
                if entry.word_type == "SIMPLE":
                    # Fetch from Pexels
                    await self._fetch_pexels_images(entry)
                else:
                    # Generate with DALL-E
                    await self._generate_dalle_image(entry)
                
                # Update database (skip in test mode)
                if not self.test_mode:
                    status = get_word_status(entry.canonical_form) or StageStatus()
                    status.image_generation = True
                    update_word_status(entry.canonical_form, status)
                
            except Exception as e:
                log.error("Image processing failed", word=entry.original, error=str(e))
                raise
        
        log.info("Stage 5 completed", count=len(entries))
    
    async def _fetch_pexels_images(self, entry: WordEntry):
        """Fetch images from Pexels for SIMPLE words."""
        if not entry.translation:
            log.warning("No translation available for Pexels search", word=entry.original)
            return
        
        image_urls = await search_pexels_images(entry.translation, count=3)
        if not image_urls:
            log.warning("No images found on Pexels", word=entry.original, query=entry.translation)
            return
        
        # Download images
        image_files = []
        for i, url in enumerate(image_urls):
            filename = generate_image_filename(entry.canonical_form, i)
            try:
                file_path = await download_image(url, filename)
                image_files.append(file_path)
            except Exception as e:
                log.error("Failed to download image", word=entry.original, url=url, error=str(e))
        
        entry.image_files = image_files
        log.info("Pexels images processed", word=entry.original, count=len(image_files))
    
    async def _generate_dalle_image(self, entry: WordEntry):
        """Generate image with DALL-E for COMPLEX words."""
        if not entry.image_prompt:
            log.warning("No image prompt available", word=entry.original)
            return
        
        try:
            image_url = await generate_image(entry.image_prompt, size="1024x1024", temperature=self.temperature)
            filename = generate_image_filename(entry.canonical_form)
            file_path = await download_image(image_url, filename)
            
            entry.image_files = [file_path]
            log.info("DALL-E image generated", word=entry.original, file=file_path)
            
        except Exception as e:
            log.error("DALL-E image generation failed", word=entry.original, error=str(e))
            raise


async def process_batch(words: List[str], force: bool = False, test_mode: bool = False, temperature: float = TEMPERATURE) -> List[ProcessingResult]:
    """Convenience function to process a batch of words."""
    pipeline = Pipeline(force=force, test_mode=test_mode, temperature=temperature)
    return await pipeline.process_batch(words) 