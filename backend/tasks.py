from datetime import datetime, timedelta
import asyncio
from sqlalchemy.orm import Session
from sqlalchemy import select
from .database import SessionLocal
from .models import WatchlistItem, AlertHistory
from .services.domain_checker import check_domain_availability  # We'll create this next
import logging

logger = logging.getLogger(__name__)


async def check_watchlist_domains():
    """Background task to check watchlist domains and send alerts."""
    while True:
        try:
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
                    # Check if domain is available
                    is_available = await check_domain_availability(
                        item.domain_name, item.domain_extension
                    )

                    if is_available and item.status == "taken":
                        # Domain has become available
                        item.status = "available"
                        item.last_checked = datetime.utcnow()

                        # Create alert
                        alert = AlertHistory(
                            watchlist_item_id=item.id,
                            alert_type="available",
                            message=f"Domain {item.domain_name}.{item.domain_extension} is now available!",
                            sent_at=datetime.utcnow(),
                        )
                        db.add(alert)

                        # Here you would trigger the actual notification
                        # (email, push notification, etc.)
                        # For now, we'll just log it
                        logger.info(f"Alert: {alert.message}")
                        alert.delivered = True

                    elif not is_available and item.status == "available":
                        # Domain has become unavailable again
                        item.status = "taken"
                        item.last_checked = datetime.utcnow()

                except Exception as e:
                    logger.error(
                        f"Error checking domain {item.domain_name}.{item.domain_extension}: {str(e)}"
                    )
                    continue

            db.commit()

        except Exception as e:
            logger.error(f"Error in watchlist checker: {str(e)}")

        finally:
            db.close()

        # Wait for 1 hour before next check
        await asyncio.sleep(3600)  # 3600 seconds = 1 hour
