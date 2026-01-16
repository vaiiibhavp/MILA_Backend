import smtplib, ssl
from email.mime.text import MIMEText
from config.basic_config import settings

#helper function for send_email
def smtp_send_email(to_email: str, subject: str, body: str, is_html: bool = False):
    msg_type = "html" if is_html else "plain"
    msg = MIMEText(body, msg_type)
    
    msg["Subject"] = subject
    msg["From"] = settings.EMAIL_FROM
    msg["To"] = to_email

    try:
        if settings.EMAIL_PORT == 465:
            context = ssl.create_default_context()
            with smtplib.SMTP_SSL(settings.EMAIL_HOST, settings.EMAIL_PORT, context=context) as server:
                server.login(settings.EMAIL_HOST_USER, settings.EMAIL_HOST_PASSWORD)
                server.sendmail(settings.EMAIL_FROM, to_email, msg.as_string())

        else:
            with smtplib.SMTP(settings.EMAIL_HOST, settings.EMAIL_PORT) as server:
                server.starttls()
                server.login(settings.EMAIL_HOST_USER, settings.EMAIL_HOST_PASSWORD)
                server.sendmail(settings.EMAIL_FROM, to_email, msg.as_string())

    except Exception as e:
        print(f"Error sending email: {e}")
        raise
