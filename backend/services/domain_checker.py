import aiohttp
import logging
import os
import json
import time
import asyncio
from typing import Tuple, Dict, Optional, List
from .email_service import send_domain_availability_email

logger = logging.getLogger(__name__)

# GoDaddy API configuration
GODADDY_API_KEY = os.getenv("GODADDY_API_KEY")
GODADDY_API_SECRET = os.getenv("GODADDY_API_SECRET")
# GoDaddy API endpoint for domain availability
# For single domains: GET request with domain as query parameter
# For multiple domains: POST request with array of domains in the body
GODADDY_API_URL = "https://api.ote-godaddy.com/v1/domains/available"

# Connection pooling configuration
# This connector will be reused across requests to improve performance
TCP_CONNECTOR = aiohttp.TCPConnector(limit=30, ssl=False, keepalive_timeout=30)

# Global session that will be initialized once and reused
_SESSION = None


async def get_session():
    """Get or create a shared aiohttp ClientSession"""
    global _SESSION
    if _SESSION is None or _SESSION.closed:
        _SESSION = aiohttp.ClientSession(
            connector=TCP_CONNECTOR, timeout=aiohttp.ClientTimeout(total=30)
        )
    return _SESSION


async def close_session():
    """Close the global session if it exists"""
    global _SESSION
    if _SESSION and not _SESSION.closed:
        await _SESSION.close()
        _SESSION = None
        logger.debug("Closed global aiohttp session")


# Simple in-memory cache for domain availability results
# Format: {domain: (result, timestamp)}
# Cache results for 24 hours (86400 seconds)
DOMAIN_CACHE = {}
CACHE_TTL = 86400  # 24 hours in seconds


def get_from_cache(domain: str) -> Optional[Dict]:
    """Get domain availability result from cache if it exists and is not expired"""
    if domain in DOMAIN_CACHE:
        result, timestamp = DOMAIN_CACHE[domain]
        if time.time() - timestamp < CACHE_TTL:
            return result
        else:
            del DOMAIN_CACHE[domain]
    return None


def add_to_cache(domain: str, result: Dict) -> None:
    """Add domain availability result to cache"""
    DOMAIN_CACHE[domain] = (result, time.time())


def clear_cache() -> None:
    """Clear the entire domain cache"""
    global DOMAIN_CACHE
    DOMAIN_CACHE = {}
    logger.info("Domain cache cleared")


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
    full_domain = f"{domain_name}.{extension}"
    logger.info(f"Checking availability for domain: {full_domain}")

    # Check cache first
    cached_result = get_from_cache(full_domain)
    if cached_result:
        logger.info(f"Cache hit for {full_domain}")
        is_available = cached_result.get("available", False)
        price_info = cached_result.get("price_info")

        # Send email notification if domain is available and email is provided
        if is_available and notify_email and price_info:
            try:
                await send_domain_availability_email(
                    notify_email, full_domain, price_info
                )
                logger.info(
                    f"Sent availability notification for {full_domain} to {notify_email}"
                )
            except Exception as email_error:
                logger.error(f"Failed to send email notification: {str(email_error)}")

        return is_available, price_info

    # If not in cache, check with API
    try:
        if not GODADDY_API_KEY or not GODADDY_API_SECRET:
            logger.error("GoDaddy API credentials not configured")
            return False, None

        # Get the shared session
        session = await get_session()

        # Use the single domain check function
        headers = {
            "Authorization": f"sso-key {GODADDY_API_KEY}:{GODADDY_API_SECRET}",
            "Content-Type": "application/json",
            "Accept": "application/json",
        }

        domain_result = await check_single_domain(full_domain, headers, session)

        # Add to cache
        add_to_cache(full_domain, domain_result)

        is_available = domain_result.get("available", False)
        price_info = domain_result.get("price_info")

        # Send email notification if domain is available and email is provided
        if is_available and notify_email and price_info:
            try:
                await send_domain_availability_email(
                    notify_email, full_domain, price_info
                )
                logger.info(
                    f"Sent availability notification for {full_domain} to {notify_email}"
                )
            except Exception as email_error:
                logger.error(f"Failed to send email notification: {str(email_error)}")

        return is_available, price_info

    except Exception as e:
        logger.error(f"Unexpected error while checking domain {full_domain}: {str(e)}")
        return False, None


async def check_multiple_domains(domains: List[str]) -> Dict[str, Dict]:
    """
    Check multiple domains using GoDaddy's bulk domain check endpoint

    Args:
        domains: List of full domain names to check (e.g. ["example.com", "example.net"])

    Returns:
        Dictionary mapping domain names to their availability info
    """
    if not domains:
        return {}

    # Log the domains we're checking (reduced verbosity)
    if len(domains) > 5:
        logger.info(f"Checking {len(domains)} domains")
    else:
        logger.info(f"Checking domains: {domains}")

    # Check cache first and collect domains that need to be checked
    results = {}
    domains_to_check = []

    for domain in domains:
        cached_result = get_from_cache(domain)
        if cached_result:
            results[domain] = cached_result
        else:
            domains_to_check.append(domain)

    # If all domains were in cache, return results
    if not domains_to_check:
        logger.info("All domains found in cache")
        return results

    # Otherwise, check remaining domains with API
    logger.info(f"Checking {len(domains_to_check)} domains with GoDaddy API")

    try:
        if not GODADDY_API_KEY or not GODADDY_API_SECRET:
            logger.error("GoDaddy API credentials not configured")
            # Return empty results for all domains
            for domain in domains_to_check:
                results[domain] = {
                    "available": False,
                    "price_info": None,
                    "error": "API credentials not configured",
                }
            return results

        # Log API credentials (masked for security) - reduced verbosity
        api_key_masked = GODADDY_API_KEY[:4] + "..." if GODADDY_API_KEY else "None"
        logger.info(f"Using GoDaddy API with key starting with: {api_key_masked}")

        headers = {
            "Authorization": f"sso-key {GODADDY_API_KEY}:{GODADDY_API_SECRET}",
            "Content-Type": "application/json",
            "Accept": "application/json",
        }

        # Try bulk API first (faster)
        try:
            # Get the shared session
            session = await get_session()

            # Prepare the payload for bulk API - GoDaddy expects an array of domain strings
            # The checkType parameter is added as a query parameter
            payload = json.dumps(domains_to_check)

            # Make the bulk API request
            async with session.post(
                GODADDY_API_URL,
                headers=headers,
                data=payload,
                params={"checkType": "FAST"},
                timeout=30,
            ) as response:
                logger.info(f"Bulk API response status: {response.status}")

                if response.status == 200:
                    response_text = await response.text()

                    try:
                        data = json.loads(response_text)

                        # The response format is different for bulk requests
                        # It returns a JSON object with a "domains" array
                        domains_data = data.get("domains", [])
                        logger.info(
                            f"Bulk API returned data for {len(domains_data)} domains"
                        )

                        # Process the results
                        for domain_info in domains_data:
                            domain = domain_info.get("domain", "")
                            if not domain:
                                logger.warning("Domain missing in API response")
                                continue

                            is_available = domain_info.get("available", False)
                            price_info = None
                            if is_available:
                                price_info = {
                                    "purchase": domain_info.get("price", 0),
                                    "renewal": domain_info.get(
                                        "price", 0
                                    ),  # GoDaddy doesn't provide renewal price in bulk response
                                }

                            domain_result = {
                                "available": is_available,
                                "price_info": price_info,
                                "error": None,
                            }

                            # Add to results and cache
                            results[domain] = domain_result
                            add_to_cache(domain, domain_result)

                        # Check if we got results for all domains
                        missing_domains = [
                            d for d in domains_to_check if d not in results
                        ]
                        if missing_domains:
                            logger.warning(
                                f"Missing results for {len(missing_domains)} domains"
                            )

                            # Fall back to individual checks for missing domains
                            await check_domains_individually(
                                missing_domains, results, headers, session
                            )

                        return results

                    except json.JSONDecodeError as json_err:
                        logger.error(f"JSON decode error for bulk API: {str(json_err)}")
                        # Fall back to individual checks
                        await check_domains_individually(
                            domains_to_check, results, headers, session
                        )
                        return results

                else:
                    logger.warning(
                        f"Bulk API failed with status {response.status}, falling back to individual checks"
                    )
                    # Fall back to individual checks
                    await check_domains_individually(
                        domains_to_check, results, headers, session
                    )
                    return results

        except Exception as bulk_error:
            logger.error(
                f"Error with bulk API: {str(bulk_error)}, falling back to individual checks"
            )
            # Fall back to individual checks
            await check_domains_individually(
                domains_to_check, results, headers, session
            )
            return results

    except Exception as e:
        logger.error(f"Unexpected error while checking domains: {str(e)}")
        # Add error results for domains that couldn't be checked
        for domain in domains_to_check:
            if domain not in results:
                results[domain] = {
                    "available": False,
                    "price_info": None,
                    "error": f"Unexpected error: {str(e)}",
                }
        return results


async def check_domains_individually(
    domains: List[str], results: Dict, headers: Dict, session: aiohttp.ClientSession
) -> None:
    """
    Check domains individually as a fallback

    Args:
        domains: List of domains to check
        results: Dictionary to store results in
        headers: API request headers
        session: aiohttp ClientSession to use
    """
    logger.info(f"Checking {len(domains)} domains individually")

    # Process domains in smaller batches to avoid overwhelming the API
    batch_size = 5
    for i in range(0, len(domains), batch_size):
        batch = domains[i : i + batch_size]
        tasks = []

        for domain in batch:
            task = asyncio.create_task(check_single_domain(domain, headers, session))
            tasks.append((domain, task))

        # Wait for all tasks in the batch to complete
        for domain, task in tasks:
            try:
                domain_result = await task
                results[domain] = domain_result
                add_to_cache(domain, domain_result)
            except Exception as e:
                logger.error(f"Error checking domain {domain}: {str(e)}")
                results[domain] = {
                    "available": False,
                    "price_info": None,
                    "error": f"Error: {str(e)}",
                }

        # Add a small delay between batches to avoid rate limiting
        if i + batch_size < len(domains):
            await asyncio.sleep(0.2)


async def check_single_domain(
    domain: str, headers: Dict, session: aiohttp.ClientSession
) -> Dict:
    """
    Check a single domain using the GoDaddy API

    Args:
        domain: Domain to check
        headers: API request headers
        session: aiohttp ClientSession to use

    Returns:
        Domain availability info
    """
    try:
        # For single domain checks, we use a GET request with the domain as a query parameter
        async with session.get(
            GODADDY_API_URL,
            params={"domain": domain, "checkType": "FAST"},
            headers=headers,
            timeout=10,
        ) as response:
            if response.status == 200:
                response_text = await response.text()

                try:
                    data = json.loads(response_text)

                    is_available = data.get("available", False)
                    price_info = None
                    if is_available:
                        price_info = {
                            "purchase": data.get("price", 0),
                            "renewal": data.get(
                                "price", 0
                            ),  # Use same price for renewal
                        }

                    return {
                        "available": is_available,
                        "price_info": price_info,
                        "error": None,
                    }

                except json.JSONDecodeError as json_err:
                    logger.error(f"JSON decode error for {domain}")
                    return {
                        "available": False,
                        "price_info": None,
                        "error": f"Invalid API response",
                    }

            elif response.status == 429:
                logger.warning(f"Rate limit exceeded for domain {domain}")
                return {
                    "available": False,
                    "price_info": None,
                    "error": "Rate limit exceeded",
                }

            else:
                logger.error(f"API error for {domain}: {response.status}")
                return {
                    "available": False,
                    "price_info": None,
                    "error": f"API error: {response.status}",
                }

    except Exception as e:
        logger.error(f"Error checking domain {domain}")
        return {
            "available": False,
            "price_info": None,
            "error": f"Error checking domain",
        }


async def cleanup_resources():
    """
    Cleanup function to be called when the application shuts down.
    Closes the global session and clears the cache.
    """
    await close_session()
    clear_cache()
    logger.info("Domain checker resources cleaned up")


# Common domain extensions to preload in cache (reduced list)
COMMON_DOMAINS = [
    "ai.com",
    "tech.com",
    "app.com",
    "data.com",
    "cloud.com",
    "ai.io",
    "tech.io",
    "app.io",
    "data.io",
    "cloud.io",
]


async def preload_common_domains():
    """
    Preload common domains into the cache to improve performance
    """
    logger.info("Preloading common domains into cache")

    # Create headers for API requests
    headers = {
        "Authorization": f"sso-key {GODADDY_API_KEY}:{GODADDY_API_SECRET}",
        "Content-Type": "application/json",
        "Accept": "application/json",
    }

    # Get the shared session
    session = await get_session()

    # Check if domains are already in cache
    domains_to_check = []
    for domain in COMMON_DOMAINS:
        if not get_from_cache(domain):
            domains_to_check.append(domain)

    if not domains_to_check:
        logger.info("All common domains already in cache")
        return

    logger.info(f"Preloading {len(domains_to_check)} common domains")

    # Check domains in batches
    batch_size = 5
    for i in range(0, len(domains_to_check), batch_size):
        batch = domains_to_check[i : i + batch_size]
        tasks = []

        for domain in batch:
            task = asyncio.create_task(check_single_domain(domain, headers, session))
            tasks.append((domain, task))

        # Wait for all tasks in the batch to complete
        for domain, task in tasks:
            try:
                domain_result = await task
                add_to_cache(domain, domain_result)
            except Exception as e:
                logger.error(f"Error preloading {domain}")

        # Add a small delay between batches
        if i + batch_size < len(domains_to_check):
            await asyncio.sleep(0.2)

    logger.info("Finished preloading common domains")
