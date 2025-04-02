import os
import logging
from mailersend import emails
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

logger = logging.getLogger(__name__)

# Email configuration
MAILERSEND_API_KEY = os.getenv("MAILERSEND_API_KEY")
SENDER_NAME = os.getenv("SENDER_NAME", "Domain Watcher")
SENDER_EMAIL = os.getenv("SENDER_EMAIL", "notifications@yourdomain.com")
REPLY_TO_EMAIL = os.getenv("REPLY_TO_EMAIL", SENDER_EMAIL)
REPLY_TO_NAME = os.getenv("REPLY_TO_NAME", SENDER_NAME)

async def send_domain_availability_email(
    recipient_email: str, domain_name: str, price_info: dict
) -> bool:
    """
    Send an email notification when a domain becomes available
    Returns True if email was sent successfully, False otherwise
    """
    logger.info(f"Preparing to send email to {recipient_email} for domain {domain_name}")
    
    # Convert price from GoDaddy format if needed (from integer in millionths to decimal)
    purchase_price = price_info.get('purchase', 0)
    renewal_price = price_info.get('renewal', 0)
    
    # Check if prices need conversion (from GoDaddy's microdollars format)
    if isinstance(purchase_price, int) and purchase_price > 1000:
        purchase_price = purchase_price / 1000000
        logger.debug(f"Converted purchase price to: ${purchase_price:.2f}")
    
    if isinstance(renewal_price, int) and renewal_price > 1000:
        renewal_price = renewal_price / 1000000
        logger.debug(f"Converted renewal price to: ${renewal_price:.2f}")
    
    try:
        if not MAILERSEND_API_KEY:
            logger.error("MailerSend API key not configured")
            return False

        # Initialize MailerSend
        mailer = emails.NewEmail(MAILERSEND_API_KEY)
        mail_body = {}

        # Set sender information
        mail_from = {
            "name": SENDER_NAME,
            "email": SENDER_EMAIL,
        }

        # Set recipient
        recipients = [
            {
                "name": recipient_email.split('@')[0],  # Use part before @ as name
                "email": recipient_email,
            }
        ]

        # Set reply-to
        reply_to = {
            "name": REPLY_TO_NAME,
            "email": REPLY_TO_EMAIL,
        }

        # Log configuration
        logger.debug(f"Sender: {SENDER_NAME} <{SENDER_EMAIL}>")
        logger.debug(f"Recipient: {recipients[0]['name']} <{recipients[0]['email']}>")
        logger.debug(f"Reply-To: {REPLY_TO_NAME} <{REPLY_TO_EMAIL}>")
        logger.debug(f"Domain: {domain_name}, Prices: Purchase=${purchase_price:.2f}, Renewal=${renewal_price:.2f}")

        # Create email body
        html_content = f"""
        <div style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto; padding: 20px; border: 1px solid #eee; border-radius: 10px; box-shadow: 0 2px 10px rgba(0,0,0,0.1);">
            <h2 style="color: #4361ee;">Good news! The domain {domain_name} is now available!</h2>
            <p>We've been monitoring this domain for you, and it's now available for registration.</p>
            
            <div style="background-color: #f8f9fa; padding: 15px; border-radius: 5px; margin: 20px 0;">
                <h3 style="margin-top: 0; color: #3a0ca3;">Price Information:</h3>
                <ul>
                    <li><strong>Purchase Price:</strong> ${purchase_price:.2f}</li>
                    <li><strong>Renewal Price:</strong> ${renewal_price:.2f}</li>
                </ul>
            </div>
            
            <p>You can register this domain now before someone else does!</p>
            
            <p>Best regards,<br>
            Your Domain Watcher</p>
        </div>
        """
        
        text_content = f"""
        Good news! The domain {domain_name} is now available for registration.

        Price Information:
        - Purchase Price: ${purchase_price:.2f}
        - Renewal Price: ${renewal_price:.2f}

        You can register this domain now before someone else does!

        Best regards,
        Your Domain Watcher
        """

        # Construct the email
        mailer.set_mail_from(mail_from, mail_body)
        mailer.set_mail_to(recipients, mail_body)
        mailer.set_subject(f"Domain {domain_name} is now available!", mail_body)
        mailer.set_html_content(html_content, mail_body)
        mailer.set_plaintext_content(text_content, mail_body)
        mailer.set_reply_to(reply_to, mail_body)

        # Send the email
        logger.info(f"Sending email through MailerSend API...")
        response = mailer.send(mail_body)
        
        # Check if email was sent successfully
        if response[0] == 202:  # 202 Accepted status code
            logger.info(f"✅ Domain availability notification sent to {recipient_email} for {domain_name}")
            return True
        else:
            logger.error(f"❌ Failed to send email notification: Status code {response[0]}")
            logger.error(f"Response details: {response[1] if len(response) > 1 else 'No details'}")
            return False

    except Exception as e:
        logger.error(f"❌ Error sending email notification: {str(e)}")
        return False
