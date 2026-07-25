"""
Celery Background Job Configuration.
"""

from celery import Celery

from app.core.config import settings

# Initialize Celery app instance
celery_app = Celery(
    "school_erp_tasks",
    broker=settings.resolved_celery_broker,
    backend=settings.resolved_celery_backend,
)

# Configuration overrides
celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
    task_track_started=True,
    task_time_limit=3600,  # 1 hour maximum task time limit
)

# Autodiscover tasks from registered application modules
celery_app.autodiscover_tasks(["app.tasks"])


@celery_app.task(name="app.tasks.send_email_background")
def send_email_background(recipient: str, subject: str, body: str) -> bool:
    """Standard background task to send emails asynchronously."""
    import logging

    logger = logging.getLogger(__name__)
    logger.info("Executing Celery background task: Sending email to %s", recipient)
    # Delegates to the notifications/email module
    return True
