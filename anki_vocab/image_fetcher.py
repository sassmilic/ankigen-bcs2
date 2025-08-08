"""Image processing functionality for the Anki vocabulary generator."""

import asyncio
from pathlib import Path
from typing import List

import structlog

from .config import TEMP_DIR
from .models import WordEntry
from .openai_client import generate_image
from .pexels_client import search_pexels_images
from .utils import download_image, generate_image_filename

log = structlog.get_logger()


class ImageFetcher:
    """Handles image generation and fetching for vocabulary words."""
    
    def __init__(self):
        pass
    
    async def fetch_pexels_images(self, entry: WordEntry):
        """Fetch images from Pexels for SIMPLE words."""
        if not entry.translation:
            log.warning("No translation available for Pexels search", word=entry.original)
            return
        
        if not entry.canonical_form or not isinstance(entry.canonical_form, str):
            log.warning("No valid canonical form available for Pexels search", word=entry.original)
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
    
    async def generate_dalle_image(self, entry: WordEntry):
        """Generate an image with DALL-E/GPT-Image and store it locally."""
        if not entry.image_prompt:
            log.warning("No image prompt available", word=entry.original)
            return

        if not entry.canonical_form or not isinstance(entry.canonical_form, str):
            log.warning("No valid canonical form available for image generation", word=entry.original)
            return

        try:
            png_bytes = await generate_image(entry.image_prompt)     # <<< bytes, not URL

            filename = generate_image_filename(entry.canonical_form)  # e.g. "škola.png"

            # Write asynchronously to avoid blocking the event-loop
            loop = asyncio.get_running_loop()
            file_path = TEMP_DIR / filename
            await loop.run_in_executor(
                None,
                lambda: file_path.write_bytes(png_bytes)
            )

            entry.image_files = [str(file_path)]
            log.info("Image generated & saved", word=entry.original, file=str(file_path))

        except Exception as e:
            # Extract detailed error information
            error_details = str(e)
            
            # Handle RetryError specifically
            if "RetryError" in str(type(e)):
                try:
                    from tenacity import RetryError
                    if isinstance(e, RetryError):
                        actual_exception = e.last_attempt.exception()
                        error_details = f"RetryError after {e.retry_state.attempt_number} attempts. Original error: {actual_exception}"
                        
                        # Try to get more details from the actual exception
                        if hasattr(actual_exception, 'response') and hasattr(actual_exception.response, 'json'):
                            try:
                                error_json = actual_exception.response.json()
                                error_details += f" - API Response: {error_json}"
                            except:
                                pass
                        if hasattr(actual_exception, 'status_code'):
                            error_details += f" - Status Code: {actual_exception.status_code}"
                        if hasattr(actual_exception, 'message'):
                            error_details += f" - Message: {actual_exception.message}"
                except:
                    pass
            
            log.error("Image generation failed", word=entry.original, error=error_details)
            raise Exception(f"Image generation failed for '{entry.original}': {error_details}") 