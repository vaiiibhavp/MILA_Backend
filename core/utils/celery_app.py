from celery import Celery
from config.basic_config import settings

from celery.schedules import crontab

# Use the prefix from settings
prefix = settings.CELERY_PREFIX


celery_app = Celery(
    "worker",
    broker=f"{settings.CELERY_BROKER_URL}/{prefix}_celery",  # Use prefix in broker URL
    backend=f"{settings.CELERY_RESULT_BACKEND}/{prefix}_celery_backend",  # Use prefix in result backend URL
)

celery_app.conf.update(
    broker_connection_retry_on_startup=True,  # Explicitly set to suppress the warning
    # Ensure proper worker isolation
    worker_prefetch_multiplier=1,  # Process one task at a time per worker
    task_acks_late=True,  # Acknowledge task completion after execution
    worker_max_tasks_per_child=1000,  # Restart worker after 1000 tasks to prevent memory leaks
    task_always_eager=False,  # Ensure tasks run in background
    task_eager_propagates=True,  # Propagate exceptions in eager mode
    # Event loop management
    worker_disable_rate_limits=True,  # Disable rate limiting for better performance
    task_serializer='json',  # Use JSON serializer
    accept_content=['json'],  # Only accept JSON content
    result_serializer='json',  # Use JSON for results
    timezone='UTC',  # Set timezone
    enable_utc=True,  # Enable UTC

)

# Set default task queue based on prefix
celery_app.conf.task_default_queue = f"{prefix}_tasks"  # Use prefix for task queue

# Optional: Define task routing
celery_app.conf.task_routes = {
    "*": {"queue": f"{prefix}_tasks"}  # Route all tasks to the prefixed queue
}

# celery_app.conf.task_routes = {"app.tasks.*": {"queue": "default"}}
# Optional: Define task routing
celery_app.conf.task_routes = {
    "*": {"queue": f"{prefix}_tasks"}  # Route all tasks to the prefixed queue
}

# Include the tasks module
celery_app.conf.update(include=["tasks"])

celery_app.conf.beat_schedule = {

    "mark_expired_subscriptions_daily": {
        "task": "tasks.mark_expired_subscriptions",
        "schedule": crontab(hour=0, minute=5),  # ⏰ 0:05 UTC daily
    },

    "subscription_expiry_notifier_daily": {
        "task": "tasks.subscription_expiry_notifier",
        "schedule": crontab(hour=0, minute=10),  # ⏰ 0:10 UTC daily
    },

    "generate_contest_cycles_daily": {
        "task": "tasks.generate_contest_cycles",
        "schedule": crontab(hour=0, minute=10),
    }
}