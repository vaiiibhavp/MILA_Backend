from core.utils.celery_app import celery_app
from core.utils.send_mail import smtp_send_email
from core.utils.response_mixin import CustomResponseMixin
import os
import asyncio
import traceback
import concurrent.futures
from datetime import datetime
import traceback
import concurrent.futures
from celery.exceptions import MaxRetriesExceededError

from services.job_services.subscription_job_service import notify_expiring_subscriptions, \
    expire_and_activate_subscriptions_job

from services.job_services.contest_tasks import generate_contest_cycles_job , get_loop

ADMIN_EMAIL = os.getenv("EMAIL_FROM")

# Celery task for run_async_in_celery
def run_async_in_celery(coroutine):
    """
    Utility function to safely run async coroutines in Celery tasks.
    Handles event loop management properly for Celery workers.
    """
    # Always use thread executor to avoid event loop conflicts
    with concurrent.futures.ThreadPoolExecutor() as executor:
        print("Running coroutine in thread executor for Celery compatibility")
        
        def run_in_thread():
            # Create a new event loop for this thread
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            try:
                return loop.run_until_complete(coroutine())
            
            finally:
                loop.close()
        
        future = executor.submit(run_in_thread)
        try:
            result = future.result()
            print(" Coroutine completed successfully in thread")
            return result
        except Exception as e:
            print(f" Error in run_async_in_celery: {str(e)}")
            print(f" Exception type: {type(e)}")
            print(f" Traceback: {traceback.format_exc()}")
            raise e


# Celery task for send_contact_us_email
@celery_app.task(name="tasks.send_contact_us_email")
def send_contact_us_email_task(first_name: str, last_name: str, email: str, mobile_number: str, message: str):
    try:
        # Define the email subject and body based on the "Contact Us" fields
        subject = f"New Contact Us Message from {first_name} {last_name}"
        body = f"Message: {message}\n\nEmail: {email}\nPhone: {mobile_number}"

        # Send the email to the admin
        smtp_send_email(to_email=ADMIN_EMAIL, subject=subject, body=body)

    except Exception as e:
        raise e


# Celery task for send_email_task
response = CustomResponseMixin()
@celery_app.task(name="tasks.send_email_task")
def send_email_task(to_email: str, subject: str, body: str, is_html: bool = False):
    smtp_send_email(to_email=to_email, subject=subject, body=body, is_html=is_html)


# Celery task for send_password_reset_email_task
@celery_app.task(name="tasks.send_password_reset_email_task")
def send_password_reset_email_task(to_email: str, subject: str, body: str):
    smtp_send_email(to_email=to_email, subject=subject, body=body)

@celery_app.task(name="tasks.subscription_expiry_notifier")
def subscription_expiry_notifier():
    try:
        asyncio.run(notify_expiring_subscriptions(3))
        return {"status": "success", "message": "subscription_expiry_notifier marked"}
    except Exception as e:
        print(f"Error marking subscription_expiry_notifier: {e}")
        return {"status": "error", "message": str(e)}

@celery_app.task(name="tasks.mark_expired_subscriptions")
def mark_expired_subscriptions():
    """
        Scheduled task to mark users with expired subscriptions as EXPIRED.
        Runs periodically (e.g. daily) to update membership status.
    """
    try:
        asyncio.run(expire_and_activate_subscriptions_job())
        return {"status": "success", "message": "mark_expired_subscriptions marked"}
    except Exception as e:
        print(f"Error marking mark_expired_subscriptions: {e}")
        return {"status": "error", "message": str(e)}

@celery_app.task(name="tasks.generate_contest_cycles")
def generate_contest_cycles():
    """
    Scheduled task to generate recurring contest cycles.
    Runs periodically (cron) and creates next contest version if due.
    """
    try:
        loop = get_loop()
        loop.run_until_complete(generate_contest_cycles_job())

        return {
            "status": "success",
            "message": "contest cycles generated successfully"
        }

    except Exception as e:
        print(f"Error in generate_contest_cycles: {e}")
        return {
            "status": "error",
            "message": str(e)
        }
