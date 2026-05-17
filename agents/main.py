"""Entry point for the Python agent orchestrator.

Phase 1: subscribes to Redis data_ready signal, then triggers analysis.
Phase 2+: actual agents run here.
"""

import asyncio
import json
import logging

import redis.asyncio as aioredis
import structlog

from config import settings, WATCHLIST
from llm.factory import create_provider_from_settings

structlog.configure(
    wrapper_class=structlog.make_filtering_bound_logger(logging.INFO),
)
log = structlog.get_logger("main")


async def on_data_ready(event: dict) -> None:
    date = event.get("date", "unknown")
    stocks = event.get("stocks", WATCHLIST)
    log.info("data_ready received", date=date, stocks=stocks)

    # Phase 2: run agents here
    # orchestrator = Orchestrator(llm=create_provider_from_settings())
    # await orchestrator.run(date=date, stocks=stocks)
    log.info("agent orchestration not yet implemented (Phase 2)")


async def listen_redis() -> None:
    client = aioredis.from_url(settings.redis_url, decode_responses=True)
    pubsub = client.pubsub()
    await pubsub.subscribe("tradingagents:data_ready")
    log.info("redis: listening on tradingagents:data_ready")

    async for message in pubsub.listen():
        if message["type"] != "message":
            continue
        try:
            event = json.loads(message["data"])
            await on_data_ready(event)
        except Exception as exc:
            log.error("error handling data_ready", error=str(exc))


async def main() -> None:
    # Validate LLM provider config on startup
    llm = create_provider_from_settings()
    log.info("llm provider ready", provider=llm.provider_name, model=llm.model_name)

    await listen_redis()


if __name__ == "__main__":
    asyncio.run(main())
