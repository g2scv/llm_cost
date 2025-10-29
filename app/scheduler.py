"""Scheduler for running the pricing pipeline every 24 hours"""

import os
import time
from datetime import datetime, timezone
import structlog
from app.config import load_config
from app.pricing_pipeline import run_once
from app.backend_sync import build_backend_sync

structlog.configure(
    processors=[
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.add_log_level,
        structlog.dev.ConsoleRenderer(),
    ]
)
logger = structlog.get_logger(__name__)


def check_and_sync_missing_models():
    """
    Check backend llm_models table for missing models and auto-sync them.

    This ensures that any models in the pricing database that aren't in the
    backend table get automatically synced.
    """
    config = load_config()

    # Only run if backend sync is enabled
    if not config.backend_supabase_url or not config.backend_supabase_service_key:
        logger.info("backend_sync_disabled", reason="no_credentials")
        return

    # Check if we should check for missing models
    check_missing = os.getenv("CHECK_MISSING_MODELS", "true").lower() == "true"
    if not check_missing:
        logger.info("missing_models_check_disabled")
        return

    try:
        from app.supabase_repo import SupabaseRepo
        from app.backend_sync import BackendSupabaseRepo, BackendSync

        logger.info("checking_for_missing_models_in_backend")

        # Get all models from pricing database
        pricing_repo = SupabaseRepo(config.supabase_url, config.supabase_service_key)

        # Get all models from backend
        backend_repo = BackendSupabaseRepo(
            config.backend_supabase_url, config.backend_supabase_service_key
        )
        backend_model_ids = set(backend_repo.list_backend_model_ids())

        # Get all models with pricing from pricing database
        from datetime import date, timedelta

        recent_date = date.today() - timedelta(
            days=7
        )  # Models with pricing in last 7 days

        result = (
            pricing_repo.client.table("model_pricing_daily")
            .select("model_id, models_catalog(or_model_slug)")
            .gte("snapshot_date", recent_date.isoformat())
            .execute()
        )

        pricing_model_slugs = set()
        for row in result.data:
            if row.get("models_catalog"):
                slug = row["models_catalog"].get("or_model_slug")
                if slug:
                    pricing_model_slugs.add(slug)

        # Find models that exist in pricing but not in backend
        missing_in_backend = pricing_model_slugs - backend_model_ids

        if missing_in_backend:
            logger.info(
                "found_missing_models_in_backend",
                count=len(missing_in_backend),
                models=list(missing_in_backend)[:10],  # Log first 10
            )

            # Trigger a sync to fill the missing models
            # The sync will run as part of the regular pipeline
            return True
        else:
            logger.info(
                "no_missing_models_in_backend", backend_count=len(backend_model_ids)
            )
            return False

    except Exception as e:
        logger.error("failed_to_check_missing_models", error=str(e), exc_info=True)
        return False


def run_scheduler():
    """Main scheduler loop - runs pipeline every N hours"""

    config = load_config()

    # Get interval from environment (default 24 hours)
    interval_hours = int(os.getenv("RUN_INTERVAL_HOURS", "24"))
    interval_seconds = interval_hours * 3600

    # Check if we should run on startup
    run_on_startup = os.getenv("RUN_ON_STARTUP", "true").lower() == "true"

    logger.info(
        "scheduler_started",
        interval_hours=interval_hours,
        run_on_startup=run_on_startup,
        backend_sync_enabled=bool(config.backend_supabase_url),
    )

    iteration = 0

    while True:
        iteration += 1
        start_time = datetime.now(timezone.utc)

        logger.info(
            "scheduler_iteration_starting",
            iteration=iteration,
            timestamp=start_time.isoformat(),
        )

        # Skip first run if run_on_startup is False
        if iteration == 1 and not run_on_startup:
            logger.info("skipping_initial_run", reason="run_on_startup=false")
        else:
            try:
                # Check for missing models in backend
                has_missing = check_and_sync_missing_models()
                if has_missing:
                    logger.info("will_sync_missing_models_in_this_run")

                # Run the main pipeline
                logger.info("running_pricing_pipeline")
                run_once(config)

                end_time = datetime.now(timezone.utc)
                duration = (end_time - start_time).total_seconds()

                logger.info(
                    "scheduler_iteration_completed",
                    iteration=iteration,
                    duration_seconds=duration,
                    next_run_in_hours=interval_hours,
                )

            except Exception as e:
                logger.error(
                    "scheduler_iteration_failed",
                    iteration=iteration,
                    error=str(e),
                    exc_info=True,
                )
                # Continue to next iteration even on error

        # Calculate sleep time
        elapsed = (datetime.now(timezone.utc) - start_time).total_seconds()
        sleep_time = max(0, interval_seconds - elapsed)

        if sleep_time > 0:
            next_run = datetime.now(timezone.utc).timestamp() + sleep_time
            next_run_dt = datetime.fromtimestamp(next_run, tz=timezone.utc)

            logger.info(
                "scheduler_sleeping",
                sleep_seconds=sleep_time,
                sleep_hours=round(sleep_time / 3600, 2),
                next_run=next_run_dt.isoformat(),
            )

            time.sleep(sleep_time)


if __name__ == "__main__":
    try:
        run_scheduler()
    except KeyboardInterrupt:
        logger.info("scheduler_stopped", reason="keyboard_interrupt")
    except Exception as e:
        logger.error("scheduler_crashed", error=str(e), exc_info=True)
        raise
