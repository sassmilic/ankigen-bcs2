"""Pexels API client for fetching images."""

import aiohttp
import structlog
from typing import List, Optional

from .config import PEXELS_API_KEY

log = structlog.get_logger()


async def search_pexels_images(query: str, count: int = 3) -> List[str]:
    """Search Pexels for images and return URLs."""
    if not PEXELS_API_KEY:
        log.warning("Pexels API key not configured, skipping image search")
        return []
    
    headers = {
        "Authorization": PEXELS_API_KEY
    }
    
    params = {
        "query": query,
        "per_page": count,
        "orientation": "landscape",
        "size": "medium"
    }
    
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(
                "https://api.pexels.com/v1/search",
                headers=headers,
                params=params
            ) as response:
                if response.status == 200:
                    data = await response.json()
                    photos = data.get("photos", [])
                    
                    image_urls = []
                    for photo in photos[:count]:
                        src = photo.get("src", {})
                        # Prefer small size for mobile Anki
                        url = src.get("small", src.get("medium", src.get("large")))
                        if url:
                            image_urls.append(url)
                    
                    log.info("Pexels search completed", query=query, found=len(image_urls))
                    return image_urls
                else:
                    log.error("Pexels API request failed", status=response.status)
                    return []
                    
    except Exception as e:
        log.error("Pexels search failed", error=str(e), query=query)
        return [] 