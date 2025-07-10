"""OpenAI API client with retry logic and rate limiting."""

import json
import openai
import structlog
from tenacity import retry, stop_after_attempt, wait_exponential_jitter
from typing import List, Dict, Any
import asyncio

from .config import OPENAI_API_KEY, MODEL_NAME, IMAGE_SIZE, TEMPERATURE

log = structlog.get_logger()

# Configure OpenAI client
client = openai.OpenAI(api_key=OPENAI_API_KEY)


async def call_chat(model: str, messages: List[Dict[str, str]]) -> str:
    """Call OpenAI Chat API with retry logic."""
    @retry(
        stop=stop_after_attempt(5),
        wait=wait_exponential_jitter(initial=1, max=32, jitter=1),
        retry=lambda exc: (
            isinstance(exc, openai.RateLimitError) or 
            isinstance(exc, openai.APITimeoutError) or
            isinstance(exc, openai.APIConnectionError) or
            "502" in str(exc) or
            "503" in str(exc) or
            "504" in str(exc)
        ),
    )
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


async def generate_image(prompt: str, size: str = IMAGE_SIZE, temperature: float = TEMPERATURE) -> str:
    """Generate an image using DALL-E."""
    @retry(
        stop=stop_after_attempt(5),
        wait=wait_exponential_jitter(initial=1, max=32, jitter=1),
        retry=lambda exc: (
            isinstance(exc, openai.RateLimitError) or 
            isinstance(exc, openai.APITimeoutError) or
            isinstance(exc, openai.APIConnectionError) or
            "502" in str(exc) or
            "503" in str(exc) or
            "504" in str(exc)
        ),
    )
    async def _make_image_call():
        loop = asyncio.get_running_loop()
        response = await loop.run_in_executor(
            None,
            lambda: client.images.generate(
                prompt=prompt,
                n=1,
                size=size,
                temperature=temperature,
            )
        )
        return response.data[0].url
    
    try:
        return await _make_image_call()
    except Exception as e:
        log.error("DALL-E image generation failed", error=str(e), prompt=prompt)
        raise 