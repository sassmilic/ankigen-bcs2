"""OpenAI API client with retry logic and rate limiting."""

import asyncio
import base64
import json
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Any

import openai
import structlog
from tenacity import (
    retry,
    stop_after_attempt,
    wait_exponential_jitter,
    retry_if_exception_type,
)

from .config import OPENAI_API_KEY, MODEL_NAME, IMAGE_SIZE, TEMPERATURE, IMAGE_PROVIDER

VALID_IMAGE_SIZES = {"1024x1024", "1792x1024", "1024x1792"}  # DALL-E 3 limits

log = structlog.get_logger()

# Configure OpenAI client
client = openai.OpenAI(api_key=OPENAI_API_KEY)


def create_openai_retry_decorator():
    """Create a retry decorator for OpenAI API calls."""
    return retry(
        stop=stop_after_attempt(5),
        wait=wait_exponential_jitter(initial=2, max=60, jitter=1),
        retry=retry_if_exception_type((
            openai.RateLimitError,
            openai.APITimeoutError,
            openai.APIConnectionError,
            openai.APIError  # Covers 502, 503, 504, etc.
        ))
    )


async def call_chat(model: str, messages: List[Dict[str, str]]) -> str:
    """Call OpenAI Chat API with retry logic."""
    from tenacity import RetryError
    
    @create_openai_retry_decorator()
    async def _make_api_call():
        loop = asyncio.get_running_loop()
        response = await loop.run_in_executor(
            None,
            lambda: client.chat.completions.create(
                model=model,
                messages=messages,
                timeout=60,
            )
        )
        return response.choices[0].message.content
    
    try:
        return await _make_api_call()
    except RetryError as e:
        # Extract the actual exception from the retry error
        actual_exception = e.last_attempt.exception()
        log.error("OpenAI API call failed after retries", 
                 error=str(actual_exception), 
                 model=model,
                 attempts=e.retry_state.attempt_number)
        raise actual_exception
    except Exception as e:
        log.error("OpenAI API call failed", error=str(e), model=model)
        raise


async def call_chat_json(model: str, messages: List[Dict[str, str]]) -> List[Dict[str, Any]]:
    """Call OpenAI Chat API and parse JSON response."""
    try:
        response = await call_chat(model, messages)
        
        # Clean the response to extract JSON
        response = response.strip()
        if response.startswith("```json"):
            response = response[7:]
        if response.endswith("```"):
            response = response[:-3]
        response = response.strip()
        
        return json.loads(response)
    except json.JSONDecodeError as e:
        log.error("Failed to parse JSON response", error=str(e), response=response)
        raise ValueError(f"Invalid JSON response: {response}")
    except Exception as e:
        # Re-raise any other exceptions (like retry errors) without wrapping
        raise


VALID_IMAGE_SIZES = {"1024x1024", "1792x1024", "1024x1792"}  # DALL-E 3 limits

async def generate_image(prompt: str,
                         size: str = "1024x1024") -> bytes:
    """
    Generate an image with the model configured in ``IMAGE_PROVIDER`` and
    return the **decoded PNG bytes**.  The function retries on transient
    OpenAI errors via ``create_openai_retry_decorator``.
    """
    if size not in VALID_IMAGE_SIZES:
        raise ValueError(f"Unsupported DALL-E size {size!r}")

    @create_openai_retry_decorator()
    async def _make_image_call() -> bytes:
        loop = asyncio.get_running_loop()
        response = await loop.run_in_executor(
            None,
            lambda: client.images.generate(
                model=IMAGE_PROVIDER,        # e.g. "gpt-image-1" or "dall-e-3"
                prompt=prompt,
                size=size,
                n=1,
            )
        )

        # Validate schema
        if not getattr(response, "data", None):
            raise RuntimeError(f"Image generation response missing data: {response}")

        b64_blob = getattr(response.data[0], "b64_json", None)
        if not b64_blob:
            raise RuntimeError(f"Image generation response missing b64_json: {response.data}")

        decoded_bytes = base64.b64decode(b64_blob)
        return decoded_bytes

    try:
        result = await _make_image_call()
        return result
    except Exception as e:
        # Extract detailed error information
        error_details = str(e)
        if hasattr(e, 'response') and hasattr(e.response, 'json'):
            try:
                error_json = e.response.json()
                error_details = f"{error_details} - API Response: {error_json}"
            except:
                pass
        if hasattr(e, 'status_code'):
            error_details = f"{error_details} - Status Code: {e.status_code}"
        if hasattr(e, 'message'):
            error_details = f"{error_details} - Message: {e.message}"
        
        log.error("Image generation failed with detailed error", error=error_details, prompt=prompt, model=IMAGE_PROVIDER)
        raise Exception(f"Image generation failed: {error_details}")