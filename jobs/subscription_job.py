from celery import shared_task
import asyncio

from services.job_services.subscription_job_service import notify_expiring_subscriptions


@shared_task
def subscription_expiry_notifier():
    asyncio.run(notify_expiring_subscriptions(3))