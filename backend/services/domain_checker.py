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
from .namesilo_service import get_namesilo_pricing

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
NAMESILO_PRICING = {}


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
    global PORKBUN_PRICING, DYNADOT_PRICING, NAMESILO_PRICING

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

            # Only get pricing for the specific extension we're checking
            pricing_tasks = []
            if not PORKBUN_PRICING:
                pricing_tasks.append(get_porkbun_pricing())
            
            # Only get Dynadot pricing for this specific extension
            # Check if we already have pricing for this extension cached
            if extension not in DYNADOT_PRICING or "error" in DYNADOT_PRICING:
                logger.info(f"Fetching Dynadot pricing only for .{extension}")
                pricing_tasks.append(get_dynadot_pricing([extension]))
            else:
                logger.info(f"Using cached Dynadot pricing for .{extension}")
            
            # Only get Namesilo pricing for this specific extension if needed
            if not NAMESILO_PRICING or extension not in NAMESILO_PRICING:
                logger.info(f"Fetching Namesilo pricing for .{extension}")
                pricing_tasks.append(get_namesilo_pricing([extension]))
            else:
                logger.info(f"Using cached Namesilo pricing for .{extension}")

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

                # Only process Dynadot results if we requested them
                if extension not in DYNADOT_PRICING or "error" in DYNADOT_PRICING:
                    result = (
                        pricing_results[pricing_index]
                        if pricing_index < len(pricing_results)
                        else None
                    )
                    if result and not isinstance(result, Exception):
                        # If DYNADOT_PRICING is empty, set it to the result
                        # Otherwise, update the existing cache with the new data
                        if not DYNADOT_PRICING:
                            DYNADOT_PRICING = result
                        else:
                            DYNADOT_PRICING.update(result)
                    pricing_index += 1

                # Only process Namesilo results if we requested them
                if not NAMESILO_PRICING or extension not in NAMESILO_PRICING:
                    result = (
                        pricing_results[pricing_index]
                        if pricing_index < len(pricing_results)
                        else None
                    )
                    if result and not isinstance(result, Exception):
                        # If NAMESILO_PRICING is empty, set it to the result
                        # Otherwise, update the existing cache with the new data
                        if not NAMESILO_PRICING:
                            NAMESILO_PRICING = result
                        else:
                            NAMESILO_PRICING.update(result)

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

            # Add Namesilo price if available
            if extension in NAMESILO_PRICING and "error" not in NAMESILO_PRICING:
                logger.info(f"Found Namesilo pricing for extension .{extension}")
                namesilo_price = NAMESILO_PRICING.get(extension, {}).get("registration")
                logger.info(f"Namesilo price for .{extension}: {namesilo_price}")

                if namesilo_price and namesilo_price != "N/A":
                    namesilo_price_converted = (
                        float(namesilo_price) * 1000000
                    )  # Convert to same format as GoDaddy
                    domain_result["providers"]["namesilo"] = namesilo_price_converted
                    logger.info(
                        f"Added Namesilo price: {namesilo_price} (converted: {namesilo_price_converted/1000000:.2f})"
                    )

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
    Check availability for multiple domains using GoDaddy's API.
    This handles batch requests and provides comprehensive information about each domain.

    Args:
        domains: List of full domain names to check (e.g. ["example.com", "example.net"])

    Returns:
        Dictionary mapping domain names to their availability info
    """
    if not domains:
        return {}

    global PORKBUN_PRICING, DYNADOT_PRICING, NAMESILO_PRICING

    # Extract unique extensions from the domains to check
    extensions_to_check = set()
    for domain in domains:
        if "." in domain:
            extension = domain.split(".")[-1]
            extensions_to_check.add(extension)
    
    logger.info(f"Checking domains with extensions: {extensions_to_check}")

    # Collect results here
    results = {}

    # Check cache first for all domains
    uncached_domains = []
    for domain in domains:
        cached_result = get_from_cache(domain)
        if cached_result:
            logger.debug(f"Cache hit for {domain}")
            results[domain] = cached_result
        else:
            uncached_domains.append(domain)

    # If all domains were in cache, return early
    if not uncached_domains:
        logger.info("All domains found in cache")
        return results

    # Set up API credentials
    if not GODADDY_API_KEY or not GODADDY_API_SECRET:
        logger.error("GoDaddy API credentials not configured")
        # Return empty results for uncached domains
        for domain in uncached_domains:
            results[domain] = {
                "available": False,
                "price_info": None,
                "error": "API credentials not configured",
            }
        return results

    try:
        # Get the shared session
        session = await get_session()

        # Set up headers for API requests
        headers = {
            "Authorization": f"sso-key {GODADDY_API_KEY}:{GODADDY_API_SECRET}",
            "Content-Type": "application/json",
            "Accept": "application/json",
        }

        # Check uncached domains in batches of 500 (GoDaddy's limit)
        batch_size = 500
        uncached_results = {}

        for i in range(0, len(uncached_domains), batch_size):
            batch = uncached_domains[i : i + batch_size]
            logger.info(f"Checking batch of {len(batch)} domains with GoDaddy API")

            try:
                # Make bulk check request
                url = f"{GODADDY_API_URL}?checkType=FAST"
                payload = {"domains": batch}

                async with session.post(
                    url, headers=headers, json=payload, timeout=20
                ) as response:
                    if response.status == 200:
                        # Process successful response
                        data = await response.json()
                        # Map domain name to result
                        domain_results = {}
                        for item in data["domains"]:
                            domain = item["domain"].lower()
                            is_available = item["available"]
                            price_info = item.get("price", None)
                            domain_results[domain] = {
                                "available": is_available,
                                "price_info": price_info,
                                "providers": {"godaddy": price_info["purchase"] if price_info else None}
                                if is_available
                                else {},
                            }
                        uncached_results.update(domain_results)
                    else:
                        # Handle failed batch
                        error_msg = await response.text()
                        logger.error(
                            f"GoDaddy API error: {response.status} - {error_msg}"
                        )
                        # Check domains individually as fallback
                        await check_domains_individually(
                            batch, uncached_results, headers, session
                        )
            except asyncio.TimeoutError:
                logger.error("Timeout when checking batch of domains")
                # Fallback: check domains individually
                await check_domains_individually(
                    batch, uncached_results, headers, session
                )
            except Exception as e:
                logger.error(f"Error checking batch of domains: {str(e)}")
                # Fallback: check domains individually
                await check_domains_individually(
                    batch, uncached_results, headers, session
                )

        # Once we have GoDaddy results, fetch pricing from other providers for available domains
        available_domains = [
            domain
            for domain, info in uncached_results.items()
            if info.get("available", False)
        ]

        if available_domains:
            logger.info(f"Found {len(available_domains)} available domains")

            # Only fetch pricing data for extensions we need
            pricing_tasks = []
            
            # Check if we need Porkbun pricing
            if not PORKBUN_PRICING or any(ext not in PORKBUN_PRICING for ext in extensions_to_check):
                pricing_tasks.append(get_porkbun_pricing())
            
            # Check if we need Dynadot pricing for specific extensions
            dynadot_extensions_needed = [ext for ext in extensions_to_check 
                                        if ext not in DYNADOT_PRICING or "error" in DYNADOT_PRICING]
            if dynadot_extensions_needed:
                logger.info(f"Fetching Dynadot pricing only for extensions: {dynadot_extensions_needed}")
                pricing_tasks.append(get_dynadot_pricing(dynadot_extensions_needed))
            else:
                logger.info(f"Using cached Dynadot pricing for all required extensions")
            
            # Check if we need Namesilo pricing for specific extensions
            namesilo_extensions_needed = [ext for ext in extensions_to_check 
                                         if not NAMESILO_PRICING or ext not in NAMESILO_PRICING]
            if namesilo_extensions_needed:
                logger.info(f"Fetching Namesilo pricing only for extensions: {namesilo_extensions_needed}")
                pricing_tasks.append(get_namesilo_pricing(namesilo_extensions_needed))
            else:
                logger.info(f"Using cached Namesilo pricing for all required extensions")

            # Also check Dynadot directly for available domains - but only for needed extensions
            available_domains_by_extension = {}
            for domain in available_domains:
                if "." in domain:
                    ext = domain.split(".")[-1]
                    if ext in dynadot_extensions_needed:
                        available_domains_by_extension.setdefault(ext, []).append(domain)
            
            # Flatten the list of domains to check with Dynadot
            dynadot_domains_to_check = []
            for domains_list in available_domains_by_extension.values():
                dynadot_domains_to_check.extend(domains_list)
            
            if dynadot_domains_to_check:
                logger.info(f"Checking {len(dynadot_domains_to_check)} domains directly with Dynadot API")
                pricing_tasks.append(check_dynadot_domains(dynadot_domains_to_check))

            # Run all pricing tasks concurrently
            if pricing_tasks:
                pricing_results = await asyncio.gather(
                    *pricing_tasks, return_exceptions=True
                )

                # Process pricing results
                pricing_index = 0
                
                # Process Porkbun results if needed
                if not PORKBUN_PRICING or any(ext not in PORKBUN_PRICING for ext in extensions_to_check):
                    result = pricing_results[pricing_index]
                    if not isinstance(result, Exception):
                        PORKBUN_PRICING = result
                    pricing_index += 1

                # Process Dynadot results if needed
                if dynadot_extensions_needed:
                    result = pricing_results[pricing_index]
                    if result and not isinstance(result, Exception):
                        # Update DYNADOT_PRICING with the new results
                        if not DYNADOT_PRICING:
                            DYNADOT_PRICING = result
                        else:
                            DYNADOT_PRICING.update(result)
                    pricing_index += 1

                # Process Namesilo results if needed
                if namesilo_extensions_needed:
                    result = pricing_results[pricing_index]
                    if result and not isinstance(result, Exception):
                        # Update NAMESILO_PRICING with the new results
                        if not NAMESILO_PRICING:
                            NAMESILO_PRICING = result
                        else:
                            NAMESILO_PRICING.update(result)
                    pricing_index += 1

                # Process direct Dynadot domain check results if we performed them
                if dynadot_domains_to_check:
                    dynadot_domain_results = pricing_results[pricing_index]
                    if not isinstance(dynadot_domain_results, Exception):
                        # Add Dynadot results to the provider data
                        for domain, dynadot_info in dynadot_domain_results.items():
                            if domain in uncached_results and uncached_results[domain].get(
                                "available", False
                            ):
                                # Get the current providers dictionary or create new one
                                providers = uncached_results[domain].get("providers", {})
                                if dynadot_info.get("available", False) and dynadot_info.get(
                                    "price"
                                ):
                                    # Convert price to match GoDaddy format (in millionths)
                                    price_float = float(dynadot_info["price"])
                                    providers["dynadot"] = price_float * 1000000
                                    logger.info(
                                        f"Added Dynadot price for {domain}: ${price_float}"
                                    )
                                uncached_results[domain]["providers"] = providers

        # Add all results to the final results dictionary and cache
        for domain, domain_result in uncached_results.items():
            results[domain] = domain_result
            add_to_cache(domain, domain_result)

        return results

    except Exception as e:
        logger.error(f"Unexpected error while checking domains: {str(e)}")
        # Add error results for domains that couldn't be checked
        for domain in uncached_domains:
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
    global PORKBUN_PRICING, DYNADOT_PRICING, NAMESILO_PRICING

    logger.info(f"Checking {len(domains)} domains individually")

    # Extract unique extensions from domains
    extensions_to_check = set()
    for domain in domains:
        if "." in domain:
            extensions_to_check.add(domain.split(".")[-1])
    
    logger.info(f"Extensions to check in individual mode: {extensions_to_check}")

    # Ensure we have the pricing data from providers, but only for needed extensions
    pricing_tasks = []
    if not PORKBUN_PRICING:
        pricing_tasks.append(get_porkbun_pricing())
        
    # Check if we need Dynadot pricing for specific extensions
    dynadot_extensions_needed = [ext for ext in extensions_to_check 
                               if ext not in DYNADOT_PRICING or "error" in DYNADOT_PRICING]
    if dynadot_extensions_needed:
        logger.info(f"Fetching Dynadot pricing only for extensions: {dynadot_extensions_needed}")
        pricing_tasks.append(get_dynadot_pricing(dynadot_extensions_needed))
    else:
        logger.info("Using cached Dynadot pricing")
        
    # Check if we need Namesilo pricing for specific extensions
    namesilo_extensions_needed = [ext for ext in extensions_to_check 
                                if not NAMESILO_PRICING or ext not in NAMESILO_PRICING]
    if namesilo_extensions_needed:
        logger.info(f"Fetching Namesilo pricing only for extensions: {namesilo_extensions_needed}")
        pricing_tasks.append(get_namesilo_pricing(namesilo_extensions_needed))
    else:
        logger.info("Using cached Namesilo pricing")

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

        if dynadot_extensions_needed:
            result = (
                pricing_results[pricing_index]
                if pricing_index < len(pricing_results)
                else None
            )
            if result and not isinstance(result, Exception):
                # Update DYNADOT_PRICING with the new results
                if not DYNADOT_PRICING:
                    DYNADOT_PRICING = result
                else:
                    DYNADOT_PRICING.update(result)
            pricing_index += 1

        if namesilo_extensions_needed:
            result = (
                pricing_results[pricing_index]
                if pricing_index < len(pricing_results)
                else None
            )
            if result and not isinstance(result, Exception):
                # Update NAMESILO_PRICING with the new results
                if not NAMESILO_PRICING:
                    NAMESILO_PRICING = result
                else:
                    NAMESILO_PRICING.update(result)
            pricing_index += 1

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
        # Group available domains by extension for Dynadot checks
        available_domains_by_extension = {}
        for domain in available_domains:
            if "." in domain:
                ext = domain.split(".")[-1]
                # Only check with Dynadot if we needed pricing for this extension
                if ext in dynadot_extensions_needed:
                    available_domains_by_extension.setdefault(ext, []).append(domain)
        
        # Flatten the list to check with Dynadot
        dynadot_domains_to_check = []
        for domains_list in available_domains_by_extension.values():
            dynadot_domains_to_check.extend(domains_list)
        
        dynadot_results = {}
        if dynadot_domains_to_check:
            logger.info(f"Checking {len(dynadot_domains_to_check)} domains with Dynadot")
            # Check domains with Dynadot concurrently
            dynadot_results = await check_dynadot_domains(dynadot_domains_to_check)

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
                # First try to get it from direct domain check results
                if domain in dynadot_results:
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
                # Otherwise try to get it from cached TLD pricing
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

                # Add Namesilo price if available
                if extension in NAMESILO_PRICING and "error" not in NAMESILO_PRICING:
                    namesilo_price = NAMESILO_PRICING.get(extension, {}).get(
                        "registration"
                    )
                    if namesilo_price and namesilo_price != "N/A":
                        logger.info(
                            f"Using Namesilo price for .{extension}: {namesilo_price}"
                        )
                        domain_result["providers"]["namesilo"] = (
                            float(namesilo_price) * 1000000
                        )  # Convert to same format as GoDaddy
                        logger.info(
                            f"Added Namesilo pricing for {domain}: ${namesilo_price}"
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
