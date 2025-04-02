from datetime import datetime, timedelta
import asyncio
from sqlalchemy.orm import Session
from sqlalchemy import select
from .database import SessionLocal
from .models import WatchlistItem, AlertHistory, User
from .services.domain_checker_forEmail import check_domain_availability
from .services.email_service import send_domain_availability_email
import logging

logger = logging.getLogger(__name__)


async def check_watchlist_domains():
    """Background task to check watchlist domains and send alerts."""
    while True:
        try:
            logger.info("Starting watchlist domain check cycle")
            db = SessionLocal()
            # Get all watchlist items with notifications enabled
            watchlist_items = (
                db.query(WatchlistItem)
                .filter(
                    WatchlistItem.notify_when_available == True,
                    WatchlistItem.status == "taken",
                )
                .all()
            )

            logger.info(f"Checking {len(watchlist_items)} watchlist domains")

            for item in watchlist_items:
                try:
                    # Get the user's email address
                    user = db.query(User).filter(User.id == item.user_id).first()
                    if not user or not user.email:
                        logger.error(f"User info missing for watchlist item {item.id}")
                        continue
                        
                    # Check if domain is available
                    domain_name = f"{item.domain_name}.{item.domain_extension}"
                    logger.info(f"Checking domain: {domain_name} for user: {user.email}")
                    
                    # Call domain availability checker
                    is_available, price_info = await check_domain_availability(
                        item.domain_name, item.domain_extension
                    )
                    
                    # Update the last checked timestamp
                    item.last_checked = datetime.utcnow()

                    if is_available and item.status == "taken":
                        # Domain has become available
                        logger.info(f"Domain {domain_name} is now available!")
                        item.status = "available"

                        # Create alert
                        alert = AlertHistory(
                            watchlist_item_id=item.id,
                            alert_type="available",
                            message=f"Domain {domain_name} is now available!",
                            sent_at=datetime.utcnow(),
                        )
                        db.add(alert)

                        # Send email notification if notify_when_available is enabled
                        if item.notify_when_available and price_info:
                            try:
                                logger.info(f"Sending email to {user.email} for domain {domain_name}")
                                email_sent = await send_domain_availability_email(
                                    user.email, 
                                    domain_name, 
                                    price_info
                                )
                                
                                # Update alert delivery status
                                alert.delivered = email_sent
                                logger.info(f"Email notification sent: {email_sent}")
                                
                            except Exception as email_error:
                                logger.error(f"Failed to send email notification: {str(email_error)}")
                                alert.delivered = False
                        else:
                            logger.info(f"Email notification disabled for {domain_name}")
                            alert.delivered = False

                    elif not is_available and item.status == "available":
                        # Domain has become unavailable again
                        logger.info(f"Domain {domain_name} is no longer available")
                        item.status = "taken"

                except Exception as e:
                    logger.error(
                        f"Error checking domain {item.domain_name}.{item.domain_extension}: {str(e)}"
                    )
                    continue

            # Commit changes to database
            db.commit()
            logger.info("Completed watchlist domain check cycle")

        except Exception as e:
            logger.error(f"Error in watchlist checker: {str(e)}")

        finally:
            db.close()

        # Wait for 1 hour before next check
        logger.info("Waiting 1 hour before next check")
        await asyncio.sleep(3600)  # 3600 seconds = 1 hour


# Add a function to manually test a single watchlist item
async def test_email_notification(email: str, domain_name: str, extension: str):
    """
    Test function to manually check a domain and send an email notification
    
    Args:
        email: Email address to send notification to
        domain_name: Domain name to check
        extension: Domain extension (e.g., 'com', 'net')
    """
    logger.info(f"Testing email notification for {domain_name}.{extension} to {email}")
    
    try:
        # Check if domain is available
        is_available, price_info = await check_domain_availability(domain_name, extension)
        
        if is_available and price_info:
            logger.info(f"Domain {domain_name}.{extension} is available, sending email")
            email_sent = await send_domain_availability_email(
                email,
                f"{domain_name}.{extension}",
                price_info
            )
            logger.info(f"Email sent successfully: {email_sent}")
            return True
        else:
            logger.info(f"Domain {domain_name}.{extension} is not available or price info missing")
            return False
            
    except Exception as e:
        logger.error(f"Error testing email notification: {str(e)}")
        return False
