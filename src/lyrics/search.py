import aiohttp
import asyncio
import logging

logger = logging.getLogger(__name__)

# LRCLIB API endpoints
LRCLIB_SEARCH = "https://lrclib.net/api/search"
LRCLIB_GET = "https://lrclib.net/api/get"

async def search_songs(query: str) -> list:
    """Search for songs using LRCLIB API"""
    try:
        timeout = aiohttp.ClientTimeout(total=15)
        async with aiohttp.ClientSession(timeout=timeout) as session:
            params = {'q': query}
            async with session.get(LRCLIB_SEARCH, params=params) as resp:
                if resp.status == 200:
                    results = await resp.json()
                    logger.info(f"Search for '{query}' returned {len(results)} results")
                    return results
                else:
                    logger.warning(f"Search API returned status {resp.status}")
                    return []
    except asyncio.TimeoutError:
        logger.error(f"Search timeout for '{query}'")
        return []
    except Exception as e:
        logger.error(f"Search error: {e}")
        return []

async def get_lyrics_by_id(song_id: str) -> dict:
    """Fetch lyrics for a specific song ID"""
    try:
        timeout = aiohttp.ClientTimeout(total=15)
        async with aiohttp.ClientSession(timeout=timeout) as session:
            async with session.get(f"{LRCLIB_GET}/{song_id}") as resp:
                if resp.status == 200:
                    song_data = await resp.json()
                    logger.info(f"Fetched lyrics for song ID {song_id}")
                    return song_data
                else:
                    logger.warning(f"Get lyrics API returned status {resp.status}")
                    return None
    except asyncio.TimeoutError:
        logger.error(f"Get lyrics timeout for ID {song_id}")
        return None
    except Exception as e:
        logger.error(f"Get lyrics error: {e}")
        return None
