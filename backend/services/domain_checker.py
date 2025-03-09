import aiohttp
import logging
import os
import json
import time
import asyncio
from typing import Tuple, Dict, Optional, List
from .email_service import send_domain_availability_email
from .porkbun_service import get_porkbun_pricing
from .dynadot_service import (
    get_dynadot_pricing,
    check_dynadot_domains,
    check_dynadot_domain,
)

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

# Cache for provider pricing data
PORKBUN_PRICING = {}
DYNADOT_PRICING = {}


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
    global PORKBUN_PRICING, DYNADOT_PRICING

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

        # Get pricing data from all providers concurrently if domain is available
        if domain_result.get("available", False):
            logger.info(f"Domain {full_domain} is available, fetching pricing data")

            # Ensure we have the pricing data from both providers
            pricing_tasks = []
            if not PORKBUN_PRICING:
                pricing_tasks.append(get_porkbun_pricing())
            if not DYNADOT_PRICING:
                pricing_tasks.append(get_dynadot_pricing())

            if pricing_tasks:
                # Run pricing data fetching concurrently
                pricing_results = await asyncio.gather(
                    *pricing_tasks, return_exceptions=True
                )

                # Process pricing results
                pricing_index = 0
                if not PORKBUN_PRICING:
                    result = pricing_results[pricing_index]
                    if not isinstance(result, Exception):
                        PORKBUN_PRICING = result
                    pricing_index += 1

                if not DYNADOT_PRICING:
                    result = (
                        pricing_results[pricing_index]
                        if pricing_index < len(pricing_results)
                        else None
                    )
                    if result and not isinstance(result, Exception):
                        DYNADOT_PRICING = result

            # Check with Dynadot for this specific domain
            dynadot_result = await check_dynadot_domain(full_domain)

            # Add provider prices to the result
            if "providers" not in domain_result:
                domain_result["providers"] = {}

            # Add GoDaddy price to providers
            godaddy_price = domain_result.get("price_info", {}).get("purchase", 0)
            domain_result["providers"]["godaddy"] = godaddy_price
            logger.info(f"Added GoDaddy price: {godaddy_price/1000000:.2f}")

            # Add Porkbun price if available
            if extension in PORKBUN_PRICING and "error" not in PORKBUN_PRICING:
                logger.info(f"Found Porkbun pricing for extension .{extension}")
                porkbun_price = PORKBUN_PRICING.get(extension, {}).get("registration")
                logger.info(f"Porkbun price for .{extension}: {porkbun_price}")

                if porkbun_price:
                    porkbun_price_converted = (
                        float(porkbun_price) * 1000000
                    )  # Convert to same format as GoDaddy
                    domain_result["providers"]["porkbun"] = porkbun_price_converted
                    logger.info(
                        f"Added Porkbun price: {porkbun_price} (converted: {porkbun_price_converted/1000000:.2f})"
                    )

            # Add Dynadot price if available
            if dynadot_result.get("available", False) and dynadot_result.get("price"):
                dynadot_price = dynadot_result.get("price")
                logger.info(f"Found Dynadot price for {full_domain}: {dynadot_price}")
                domain_result["providers"]["dynadot"] = (
                    float(dynadot_price) * 1000000
                )  # Convert to same format as GoDaddy
                logger.info(f"Added Dynadot price: {dynadot_price}")
            elif extension in DYNADOT_PRICING and "error" not in DYNADOT_PRICING:
                dynadot_price = DYNADOT_PRICING.get(extension)
                if dynadot_price:
                    logger.info(
                        f"Using cached Dynadot price for .{extension}: {dynadot_price}"
                    )
                    domain_result["providers"]["dynadot"] = (
                        float(dynadot_price) * 1000000
                    )  # Convert to same format as GoDaddy
                    logger.info(f"Added Dynadot price from cache: {dynadot_price}")

            # Log the full providers object
            logger.info(f"Final providers object: {domain_result.get('providers', {})}")

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
    global PORKBUN_PRICING, DYNADOT_PRICING

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

                        # Process the results first to identify available domains
                        available_domains = []
                        domain_results = {}

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
                                # Add to available domains list for Dynadot check
                                available_domains.append(domain)

                            domain_result = {
                                "available": is_available,
                                "price_info": price_info,
                                "error": None,
                            }

                            # Add provider pricing if domain is available
                            if is_available:
                                # Extract extension from domain
                                parts = domain.split(".")
                                if len(parts) > 1:
                                    extension = parts[-1]

                                    # Add provider prices
                                    domain_result["providers"] = {}

                                    # Add GoDaddy price
                                    godaddy_price = price_info.get("purchase", 0)
                                    domain_result["providers"][
                                        "godaddy"
                                    ] = godaddy_price

                            # Store the result
                            domain_results[domain] = domain_result

                        # Only check available domains with other providers
                        logger.info(f"Found {len(available_domains)} available domains")
                        if available_domains:
                            # Get pricing data from all providers concurrently
                            logger.info(
                                "Fetching pricing data from all providers concurrently"
                            )

                            # Ensure we have the pricing data from both providers
                            pricing_tasks = []
                            if not PORKBUN_PRICING:
                                pricing_tasks.append(get_porkbun_pricing())
                            if not DYNADOT_PRICING:
                                pricing_tasks.append(get_dynadot_pricing())

                            if pricing_tasks:
                                # Run pricing data fetching concurrently
                                pricing_results = await asyncio.gather(
                                    *pricing_tasks, return_exceptions=True
                                )

                                # Process pricing results
                                pricing_index = 0
                                if not PORKBUN_PRICING:
                                    result = pricing_results[pricing_index]
                                    if not isinstance(result, Exception):
                                        PORKBUN_PRICING = result
                                    pricing_index += 1

                                if not DYNADOT_PRICING:
                                    result = (
                                        pricing_results[pricing_index]
                                        if pricing_index < len(pricing_results)
                                        else None
                                    )
                                    if result and not isinstance(result, Exception):
                                        DYNADOT_PRICING = result

                            # Check domains with both providers concurrently
                            logger.info(
                                "Checking available domains with Porkbun and Dynadot concurrently"
                            )
                            dynadot_task = check_dynadot_domains(available_domains)

                            # Run domain checks concurrently
                            dynadot_results = await dynadot_task

                            # Add provider pricing to the results
                            for domain in available_domains:
                                domain_result = domain_results[domain]
                                parts = domain.split(".")
                                if len(parts) > 1:
                                    extension = parts[-1]

                                    # Add Porkbun price if available
                                    if (
                                        extension in PORKBUN_PRICING
                                        and "error" not in PORKBUN_PRICING
                                    ):
                                        porkbun_price = PORKBUN_PRICING.get(
                                            extension, {}
                                        ).get("registration")
                                        if porkbun_price:
                                            domain_result["providers"]["porkbun"] = (
                                                float(porkbun_price) * 1000000
                                            )  # Convert to same format as GoDaddy
                                            logger.info(
                                                f"Added Porkbun pricing for {domain}: ${porkbun_price}"
                                            )

                                    # Add Dynadot price if available
                                    dynadot_domain_info = dynadot_results.get(
                                        domain, {}
                                    )
                                    if dynadot_domain_info.get(
                                        "available", False
                                    ) and dynadot_domain_info.get("price"):
                                        dynadot_price = dynadot_domain_info.get("price")
                                        logger.info(
                                            f"Found Dynadot price for {domain}: {dynadot_price}"
                                        )
                                        domain_result["providers"]["dynadot"] = (
                                            float(dynadot_price) * 1000000
                                        )  # Convert to same format as GoDaddy
                                        logger.info(
                                            f"Added Dynadot pricing for {domain}: ${dynadot_price}"
                                        )
                                    elif (
                                        extension in DYNADOT_PRICING
                                        and "error" not in DYNADOT_PRICING
                                    ):
                                        dynadot_price = DYNADOT_PRICING.get(extension)
                                        if dynadot_price:
                                            logger.info(
                                                f"Using cached Dynadot price for .{extension}: {dynadot_price}"
                                            )
                                            domain_result["providers"]["dynadot"] = (
                                                float(dynadot_price) * 1000000
                                            )  # Convert to same format as GoDaddy
                                            logger.info(
                                                f"Added Dynadot pricing from cache for {domain}: ${dynadot_price}"
                                            )

                        # Add all results to the final results dictionary and cache
                        for domain, domain_result in domain_results.items():
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
    global PORKBUN_PRICING, DYNADOT_PRICING

    logger.info(f"Checking {len(domains)} domains individually")

    # Get pricing data from all providers concurrently
    logger.info("Fetching pricing data from all providers concurrently")

    # Ensure we have the pricing data from both providers
    pricing_tasks = []
    if not PORKBUN_PRICING:
        pricing_tasks.append(get_porkbun_pricing())
    if not DYNADOT_PRICING:
        pricing_tasks.append(get_dynadot_pricing())

    if pricing_tasks:
        # Run pricing data fetching concurrently
        pricing_results = await asyncio.gather(*pricing_tasks, return_exceptions=True)

        # Process pricing results
        pricing_index = 0
        if not PORKBUN_PRICING:
            result = pricing_results[pricing_index]
            if not isinstance(result, Exception):
                PORKBUN_PRICING = result
            pricing_index += 1

        if not DYNADOT_PRICING:
            result = (
                pricing_results[pricing_index]
                if pricing_index < len(pricing_results)
                else None
            )
            if result and not isinstance(result, Exception):
                DYNADOT_PRICING = result

    # Process domains in smaller batches to avoid overwhelming the API
    batch_size = 5
    available_domains = []
    domain_results = {}

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

                # Add provider pricing if domain is available
                if domain_result.get("available", False):
                    # Add to available domains list for Dynadot check
                    available_domains.append(domain)

                    # Extract extension from domain
                    parts = domain.split(".")
                    if len(parts) > 1:
                        extension = parts[-1]

                        # Add provider prices
                        domain_result["providers"] = {}

                        # Add GoDaddy price
                        godaddy_price = domain_result.get("price_info", {}).get(
                            "purchase", 0
                        )
                        domain_result["providers"]["godaddy"] = godaddy_price

                # Store the result
                domain_results[domain] = domain_result

            except Exception as e:
                logger.error(f"Error checking domain {domain}: {str(e)}")
                domain_results[domain] = {
                    "available": False,
                    "price_info": None,
                    "error": f"Error: {str(e)}",
                }

        # Add a small delay between batches to avoid rate limiting
        if i + batch_size < len(domains):
            await asyncio.sleep(0.2)

    # Only check available domains with other providers
    logger.info(f"Found {len(available_domains)} available domains")
    if available_domains:
        # Check domains with Dynadot concurrently
        logger.info("Checking available domains with Dynadot")
        dynadot_task = check_dynadot_domains(available_domains)

        # Run domain checks
        dynadot_results = await dynadot_task

        # Add provider pricing to the results
        for domain in available_domains:
            domain_result = domain_results[domain]
            parts = domain.split(".")
            if len(parts) > 1:
                extension = parts[-1]

                # Add Porkbun price if available
                if extension in PORKBUN_PRICING and "error" not in PORKBUN_PRICING:
                    porkbun_price = PORKBUN_PRICING.get(extension, {}).get(
                        "registration"
                    )
                    if porkbun_price:
                        domain_result["providers"]["porkbun"] = (
                            float(porkbun_price) * 1000000
                        )  # Convert to same format as GoDaddy
                        logger.info(
                            f"Added Porkbun pricing for {domain}: ${porkbun_price}"
                        )

                # Add Dynadot price if available
                dynadot_domain_info = dynadot_results.get(domain, {})
                if dynadot_domain_info.get(
                    "available", False
                ) and dynadot_domain_info.get("price"):
                    dynadot_price = dynadot_domain_info.get("price")
                    logger.info(f"Found Dynadot price for {domain}: {dynadot_price}")
                    domain_result["providers"]["dynadot"] = (
                        float(dynadot_price) * 1000000
                    )  # Convert to same format as GoDaddy
                    logger.info(f"Added Dynadot pricing for {domain}: ${dynadot_price}")
                elif extension in DYNADOT_PRICING and "error" not in DYNADOT_PRICING:
                    dynadot_price = DYNADOT_PRICING.get(extension)
                    if dynadot_price:
                        logger.info(
                            f"Using cached Dynadot price for .{extension}: {dynadot_price}"
                        )
                        domain_result["providers"]["dynadot"] = (
                            float(dynadot_price) * 1000000
                        )  # Convert to same format as GoDaddy
                        logger.info(
                            f"Added Dynadot pricing from cache for {domain}: ${dynadot_price}"
                        )

    # Add all results to the final results dictionary and cache
    for domain, domain_result in domain_results.items():
        results[domain] = domain_result
        add_to_cache(domain, domain_result)


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
