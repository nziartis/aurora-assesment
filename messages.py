import asyncio
import logging
import time
from dataclasses import dataclass

import httpx

logger = logging.getLogger(__name__)

MESSAGES_API = "https://november7-730026606190.europe-west1.run.app/messages/"
CACHE_TTL = 600  # seconds
PAGE_SIZE = 100
MAX_RETRIES = 5
RETRY_SLEEP = 2.0


@dataclass
class Message:
    user_name: str
    timestamp: str
    message: str


_cache: dict[str, list[Message]] = {}
_fetched_at: float = 0.0
_lock = asyncio.Lock()


async def _fetch_page(client: httpx.AsyncClient, skip: int) -> httpx.Response:
    for attempt in range(MAX_RETRIES):
        response = await client.get(MESSAGES_API, params={"skip": skip, "limit": PAGE_SIZE})
        if response.status_code == 200:
            return response
        logger.warning("skip=%d attempt %d/%d returned %d", skip, attempt + 1, MAX_RETRIES, response.status_code)
        if attempt < MAX_RETRIES - 1:
            await asyncio.sleep(RETRY_SLEEP)
    return response


async def refresh() -> None:
    global _cache, _fetched_at

    async with httpx.AsyncClient(timeout=30.0) as client:
        skip = 0
        all_messages: list[Message] = []

        while True:
            response = await _fetch_page(client, skip)
            if response.status_code != 200:
                logger.warning("Stopping pagination at skip=%d after %d retries — %d messages collected.", skip, MAX_RETRIES, len(all_messages))
                break
            data = response.json()
            items = data["items"]

            all_messages.extend(
                Message(
                    user_name=item["user_name"],
                    timestamp=item["timestamp"],
                    message=item["message"],
                )
                for item in items
            )

            skip += len(items)
            if skip >= data["total"]:
                break

    grouped: dict[str, list[Message]] = {}
    for msg in all_messages:
        grouped.setdefault(msg.user_name, []).append(msg)

    _cache = grouped
    _fetched_at = time.monotonic()
    logger.info("Cache refreshed: %d members, %d messages total.", len(_cache), len(all_messages))


async def get_all() -> dict[str, list[Message]]:
    async with _lock:
        if time.monotonic() - _fetched_at > CACHE_TTL:
            await refresh()
    return _cache


def find_user(question: str, data: dict[str, list[Message]]) -> list[Message] | None:
    q = question.lower()
    best_name: str | None = None
    best_score = 0

    for user_name in data:
        parts = [p for p in user_name.lower().split() if len(p) > 2]
        score = sum(1 for p in parts if p in q)
        if score > best_score:
            best_score = score
            best_name = user_name

    return data[best_name] if best_name else None
