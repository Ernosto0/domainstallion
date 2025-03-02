import aiohttp
import logging
import os
from typing import Tuple, Dict, Optional
from .email_service import send_domain_availability_email

logger = logging.getLogger(__name__)

# GoDaddy API configuration
GODADDY_API_KEY = os.getenv("GODADDY_API_KEY")
GODADDY_API_SECRET = os.getenv("GODADDY_API_SECRET")
GODADDY_API_URL = "https://api.ote-godaddy.com/v1/domains/available"


async def check_domain_availability(
    domain_name: str, extension: str, notify_email: Optional[str] = None
) -> Tuple[bool, Optional[Dict]]:
    """
    Check domain availability using GoDaddy's API
    Returns a tuple of (is_available, price_info)
    If notify_email is provided, sends an email notification when domain is available
    """
    try:
        full_domain = f"{domain_name}.{extension}"

        if not GODADDY_API_KEY or not GODADDY_API_SECRET:
            logger.error("GoDaddy API credentials not configured")
            return False, None

        headers = {
            "Authorization": f"sso-key {GODADDY_API_KEY}:{GODADDY_API_SECRET}",
            "Content-Type": "application/json",
        }

        async with aiohttp.ClientSession() as session:
            async with session.get(
                GODADDY_API_URL, params={"domain": full_domain}, headers=headers
            ) as response:
                if response.status == 200:
                    data = await response.json()
                    is_available = data.get("available", False)
                    price_info = (
                        {
                            "purchase": data.get("price", 0),
                            "renewal": data.get("renewalPrice", 0),
                        }
                        if is_available
                        else None
                    )

                    logger.info(
                        f"Domain check for {full_domain}: Available={is_available}"
                    )

                    # Send email notification if domain is available and email is provided
                    if is_available and notify_email and price_info:
                        await send_domain_availability_email(
                            notify_email, full_domain, price_info
                        )

                    return is_available, price_info
                else:
                    logger.error(
                        f"GoDaddy API error for {full_domain}: {response.status}"
                    )
                    return False, None

    except Exception as e:
        logger.error(f"Error checking domain availability: {str(e)}")
        return False, None
