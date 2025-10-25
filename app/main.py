"""Main entrypoint and scheduler for pricing tracker"""

import asyncio
import sys
from datetime import datetime, timedelta, timezone
import structlog
from structlog.stdlib import LoggerFactory

from app.config import load_config
from app.pricing_pipeline import run_once

# Configure structured logging
structlog.configure(
    processors=[
        structlog.stdlib.add_log_level,
        structlog.stdlib.add_logger_name,
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.StackInfoRenderer(),
        structlog.processors.format_exc_info,
        structlog.processors.JSONRenderer(),
    ],
    context_class=dict,
    logger_factory=LoggerFactory(),
    cache_logger_on_first_use=True,
)

logger = structlog.get_logger(__name__)


async def main_loop():
    """
    Main event loop - runs pricing collection every 24 hours

    This function is designed to run continuously in a Docker container
    or can be called once from cron/systemd timer
    """
    config = load_config()

    logger.info("pricing_tracker_started", log_level=config.log_level)

    # Run immediately on startup
    try:
        logger.info("starting_initial_run")
        await run_once(config)
        logger.info("initial_run_completed")
    except Exception as e:
        logger.error("initial_run_failed", error=str(e), exc_info=True)
        # Don't exit on first failure - wait and retry

    # Loop every 24 hours
    while True:
        next_run = datetime.now(timezone.utc) + timedelta(hours=24)
        logger.info("scheduling_next_run", next_run=next_run.isoformat())

        # Sleep until next run
        await asyncio.sleep(24 * 60 * 60)

        try:
            logger.info("starting_scheduled_run")
            await run_once(config)
            logger.info("scheduled_run_completed")
        except Exception as e:
            logger.error("scheduled_run_failed", error=str(e), exc_info=True)
            # Continue to next iteration


async def run_once_and_exit():
    """
    Run pricing collection once and exit

    This is useful for cron/systemd timer setups where you want
    the process to exit after each run
    """
    config = load_config()

    logger.info("pricing_tracker_single_run")

    try:
        await run_once(config)
        logger.info("single_run_completed")
        sys.exit(0)
    except Exception as e:
        logger.error("single_run_failed", error=str(e), exc_info=True)
        sys.exit(1)


def main():
    """
    Main entry point

    Behavior controlled by command line args:
    - No args: Run continuous loop (for Docker)
    - --once: Run once and exit (for cron/systemd)
    """
    if len(sys.argv) > 1 and sys.argv[1] == "--once":
        asyncio.run(run_once_and_exit())
    else:
        asyncio.run(main_loop())


if __name__ == "__main__":
    main()
