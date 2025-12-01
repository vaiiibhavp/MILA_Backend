import smtplib
from email.mime.text import MIMEText
from config.basic_config import settings

#helper function for send_email
def send_email(to_email: str, subject: str, body: str):
    msg = MIMEText(body, "plain")
    msg["Subject"] = subject
    msg["From"] = settings.EMAIL_FROM
    msg["To"] = to_email

    try:
        with smtplib.SMTP_SSL(settings.EMAIL_HOST, settings.EMAIL_PORT, timeout=20) as server:
            server.set_debuglevel(1)
            server.login(
                settings.EMAIL_HOST_USER.strip(),
                settings.EMAIL_HOST_PASSWORD.strip()
            )
            server.sendmail(
                settings.EMAIL_FROM,
                [to_email],
                msg.as_string()
            )

    except Exception as e:
        print(f"Error sending email: {e}")
        raise
