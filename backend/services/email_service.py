import os
import smtplib
import logging
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

logger = logging.getLogger(__name__)

# Email configuration
SMTP_SERVER = os.getenv("SMTP_SERVER", "smtp.gmail.com")
SMTP_PORT = int(os.getenv("SMTP_PORT", "587"))
SMTP_USERNAME = os.getenv("SMTP_USERNAME")
SMTP_PASSWORD = os.getenv("SMTP_PASSWORD")
SENDER_EMAIL = os.getenv("SENDER_EMAIL")


async def send_domain_availability_email(
    recipient_email: str, domain_name: str, price_info: dict
) -> bool:
    """
    Send an email notification when a domain becomes available
    Returns True if email was sent successfully, False otherwise
    """
    try:
        if not all([SMTP_USERNAME, SMTP_PASSWORD, SENDER_EMAIL]):
            logger.error("Email credentials not configured")
            return False

        # Create message
        message = MIMEMultipart()
        message["From"] = SENDER_EMAIL
        message["To"] = recipient_email
        message["Subject"] = f"Domain {domain_name} is now available!"

        # Create email body
        body = f"""
        Good news! The domain {domain_name} is now available for registration.

        Price Information:
        - Purchase Price: ${price_info['purchase']}
        - Renewal Price: ${price_info['renewal']}

        You can register this domain now before someone else does!

        Best regards,
        Your Domain Watcher
        """

        message.attach(MIMEText(body, "plain"))

        # Send email
        with smtplib.SMTP(SMTP_SERVER, SMTP_PORT) as server:
            server.starttls()
            server.login(SMTP_USERNAME, SMTP_PASSWORD)
            server.send_message(message)

        logger.info(
            f"Domain availability notification sent to {recipient_email} for {domain_name}"
        )
        return True

    except Exception as e:
        logger.error(f"Error sending email notification: {str(e)}")
        return False
