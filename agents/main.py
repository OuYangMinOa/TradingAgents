"""Python agent orchestrator entry point.

Listens for Redis data_ready signals from the Go collector,
then runs the full multi-agent pipeline for each stock in the watchlist.
"""

import asyncio
import json
import logging
from datetime import date

import redis.asyncio as aioredis
import structlog

from config import WATCHLIST, settings
from llm.factory import create_provider_from_settings
from orchestrator import Orchestrator

structlog.configure(
    wrapper_class=structlog.make_filtering_bound_logger(logging.INFO),
)
log = structlog.get_logger("main")


async def on_data_ready(orchestrator: Orchestrator, event: dict) -> None:
    run_date_str = event.get("date")
    stocks = event.get("stocks", WATCHLIST)

    try:
        run_date = date.fromisoformat(run_date_str) if run_date_str else date.today()
    except ValueError:
        run_date = date.today()

    log.info("data_ready received", date=run_date.isoformat(), stocks=len(stocks))
    await orchestrator.run(run_date=run_date, stocks=stocks)


async def listen_redis(orchestrator: Orchestrator) -> None:
    client = aioredis.from_url(settings.redis_url, decode_responses=True)
    pubsub = client.pubsub()
    await pubsub.subscribe("tradingagents:data_ready")
    log.info("listening", channel="tradingagents:data_ready")

    async for message in pubsub.listen():
        if message["type"] != "message":
            continue
        try:
            event = json.loads(message["data"])
            await on_data_ready(orchestrator, event)
        except Exception as exc:
            log.error("pipeline error", error=str(exc))


async def main() -> None:
    llm = create_provider_from_settings()
    log.info("llm ready", provider=llm.provider_name, model=llm.model_name)

    orchestrator = Orchestrator(llm)

    if settings.dry_run:
        log.info("DRY_RUN=true — will produce reports but not place orders")

    await listen_redis(orchestrator)


if __name__ == "__main__":
    asyncio.run(main())
