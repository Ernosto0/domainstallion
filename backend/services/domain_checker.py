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


class DomainCheckError(Exception):
    def __init__(
        self, message: str, domain: str, error_code: str, details: Optional[Dict] = None
    ):
        self.message = message
        self.domain = domain
        self.error_code = error_code
        self.details = details or {}
        super().__init__(message)


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
            raise DomainCheckError(
                message="GoDaddy API credentials not configured",
                domain=full_domain,
                error_code="API_CREDENTIALS_MISSING",
            )

        headers = {
            "Authorization": f"sso-key {GODADDY_API_KEY}:{GODADDY_API_SECRET}",
            "Content-Type": "application/json",
        }

        async with aiohttp.ClientSession() as session:
            try:
                async with session.get(
                    GODADDY_API_URL,
                    params={"domain": full_domain},
                    headers=headers,
                    timeout=30,  # Add timeout
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
                            try:
                                await send_domain_availability_email(
                                    notify_email, full_domain, price_info
                                )
                            except Exception as email_error:
                                logger.error(
                                    f"Failed to send email notification: {str(email_error)}"
                                )
                                # Don't raise exception here, as the domain check was successful

                        return is_available, price_info

                    elif response.status == 429:
                        raise DomainCheckError(
                            message="Rate limit exceeded for GoDaddy API",
                            domain=full_domain,
                            error_code="RATE_LIMIT_EXCEEDED",
                            details={
                                "retry_after": response.headers.get("Retry-After")
                            },
                        )
                    else:
                        error_text = await response.text()
                        raise DomainCheckError(
                            message=f"GoDaddy API error: {response.status}",
                            domain=full_domain,
                            error_code="API_ERROR",
                            details={
                                "status_code": response.status,
                                "response": error_text,
                            },
                        )

            except aiohttp.ClientError as e:
                raise DomainCheckError(
                    message="Network error while checking domain",
                    domain=full_domain,
                    error_code="NETWORK_ERROR",
                    details={"error": str(e)},
                )

    except DomainCheckError:
        raise
    except Exception as e:
        raise DomainCheckError(
            message="Unexpected error while checking domain",
            domain=full_domain,
            error_code="UNEXPECTED_ERROR",
            details={"error": str(e)},
        )
