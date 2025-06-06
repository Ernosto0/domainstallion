import os
import json
import logging
import aiohttp
import asyncio
import time
import re
from typing import Dict, List, Optional

logger = logging.getLogger(__name__)

# Dynadot API configuration
DYNADOT_API_KEY = os.getenv("DYNADOT_API_KEY")
DYNADOT_API_URL = "https://api.dynadot.com/api3.json"

# Cache for Dynadot pricing data
# Format: {tld: price, ...}
DYNADOT_PRICING_CACHE = {}
CACHE_TIMESTAMP = 0
CACHE_TTL = 86400  # 24 hours in seconds

# Retry settings
MAX_RETRIES = 3
DELAY_BETWEEN_REQUESTS = 0.1  # Adjust delay based on API rate limits


def extract_registration_price(price_string: str) -> Optional[float]:
    """
    Extract the registration price from the Dynadot price string.
    Example input: "Registration Price: 10.86 in USD and Renewal price: 10.86 in USD and Domain is not a Premium Domain"
    Returns: 10.86
    """
    if not price_string:
        return None

    # Add debug logging
    logger.debug(f"Extracting price from price string: {price_string}")

    # Use regex to extract the registration price - improve pattern to handle more formats
    match = re.search(r"Registration Price: (\d+\.\d+)", price_string)
    if match:
        try:
            price = float(match.group(1))
            logger.debug(f"Successfully extracted price: {price}")
            return price
        except (ValueError, TypeError):
            logger.error(f"Failed to convert price to float: {match.group(1)}")
            return None
    else:
        # Try alternative pattern that might be used for some TLDs
        alt_match = re.search(r"(\d+\.\d+) USD", price_string)
        if alt_match:
            try:
                price = float(alt_match.group(1))
                logger.debug(f"Extracted price using alternative pattern: {price}")
                return price
            except (ValueError, TypeError):
                logger.error(f"Failed to convert alternative price to float: {alt_match.group(1)}")
                return None
        
        logger.warning(f"No price pattern matched in string: {price_string}")
        return None


async def get_dynadot_pricing(requested_tlds=None) -> Dict:
    """
    Fetch domain pricing from Dynadot API asynchronously.
    Returns a dictionary of TLDs with their pricing information.
    Caches results for 24 hours to reduce API calls.
    
    Args:
        requested_tlds: Optional list of TLDs to check pricing for.
                       If None, only checks pricing for common TLDs.
    """
    global DYNADOT_PRICING_CACHE, CACHE_TIMESTAMP

    # Check if we have cached data that's still valid
    current_time = time.time()
    
    # Common TLDs to check for pricing if no specific TLDs are requested
    common_tlds = ["com", "net", "org", "io", "ai", "app", "dev", "tech"]
    
    # If requested_tlds is provided, only check those TLDs
    tlds_to_check = requested_tlds if requested_tlds else common_tlds
    
    # If we have a valid cache, return only the requested TLDs from it
    if DYNADOT_PRICING_CACHE and (current_time - CACHE_TIMESTAMP < CACHE_TTL):
        logger.debug("Using cached Dynadot pricing data")
        # If we have requested specific TLDs, only return those
        if requested_tlds:
            logger.info(f"Returning cached pricing for requested TLDs: {requested_tlds}")
            result = {tld: DYNADOT_PRICING_CACHE.get(tld) for tld in requested_tlds if tld in DYNADOT_PRICING_CACHE}
            logger.debug(f"Cached prices being returned: {result}")
            return result
        logger.debug(f"Full cache contents: {DYNADOT_PRICING_CACHE}")
        return DYNADOT_PRICING_CACHE

    # If we're here, we need to fetch new pricing data
    logger.info(f"Fetching Dynadot pricing data for TLDs: {tlds_to_check}")
    logger.info(f"DYNADOT_API_KEY exists: {bool(DYNADOT_API_KEY)}")

    if not DYNADOT_API_KEY:
        logger.error("Dynadot API key not configured")
        return {"error": "API key not configured"}
    
    # Create a pricing dictionary
    pricing_data = {}

    try:
        async with aiohttp.ClientSession() as session:
            # Check pricing for requested TLDs
            for tld in tlds_to_check:
                # If we already have this TLD in cache and it's valid, skip checking
                if tld in DYNADOT_PRICING_CACHE and (current_time - CACHE_TIMESTAMP < CACHE_TTL):
                    pricing_data[tld] = DYNADOT_PRICING_CACHE[tld]
                    logger.debug(f"Using cached price for .{tld}: ${DYNADOT_PRICING_CACHE[tld]}")
                    continue
                
                # Create a sample domain for pricing check
                sample_domain = f"example{int(time.time())}.{tld}"

                params = {
                    "key": DYNADOT_API_KEY,
                    "command": "search",
                    "show_price": "1",
                    "currency": "USD",
                    "domain0": sample_domain,
                }

                try:
                    logger.debug(f"Sending request to Dynadot API for .{tld} pricing")
                    async with session.get(
                        DYNADOT_API_URL, params=params, timeout=10
                    ) as response:
                        if response.status == 200:
                            response_text = await response.text()
                            logger.debug(
                                f"Dynadot API response for .{tld}: {response_text[:200]}..."
                            )

                            try:
                                data = json.loads(response_text)
                                search_results = data.get("SearchResponse", {}).get(
                                    "SearchResults", []
                                )

                                if search_results and len(search_results) > 0:
                                    result = search_results[0]
                                    if result.get("Available") == "yes":
                                        price_string = result.get("Price")
                                        logger.debug(
                                            f"Raw price string for .{tld}: {price_string}"
                                        )

                                        if price_string:
                                            # Extract the registration price from the string
                                            registration_price = (
                                                extract_registration_price(price_string)
                                            )

                                            if registration_price:
                                                # Store the price in our cache
                                                pricing_data[tld] = registration_price
                                                logger.info(
                                                    f"Dynadot price for .{tld}: ${registration_price}"
                                                )
                                            else:
                                                logger.warning(
                                                    f"Could not extract registration price from: {price_string}"
                                                )
                                else:
                                    logger.warning(
                                        f"No search results found for .{tld}"
                                    )
                            except json.JSONDecodeError as json_err:
                                logger.error(
                                    f"JSON decode error for .{tld}: {str(json_err)}"
                                )
                        else:
                            logger.error(
                                f"Dynadot API error for .{tld}: {response.status}"
                            )

                        # Add a small delay to avoid rate limiting
                        await asyncio.sleep(DELAY_BETWEEN_REQUESTS)

                except Exception as e:
                    logger.error(f"Error fetching Dynadot pricing for .{tld}: {str(e)}")

            # Update cache with new data, preserving existing cache data
            DYNADOT_PRICING_CACHE.update(pricing_data)
            CACHE_TIMESTAMP = current_time

            logger.info(
                f"Successfully cached pricing for {len(pricing_data)} TLDs from Dynadot"
            )
            
            logger.debug(f"Updated Dynadot pricing cache: {DYNADOT_PRICING_CACHE}")

            # Only return requested TLDs if specified
            if requested_tlds:
                logger.info(f"Returning pricing for requested TLDs: {requested_tlds}")
                result = {tld: pricing_data.get(tld) for tld in requested_tlds if tld in pricing_data}
                logger.debug(f"Prices being returned: {result}")
                return result
            
            logger.debug(f"Returning all pricing data: {pricing_data}")
            return pricing_data

    except Exception as e:
        logger.error(f"Error fetching Dynadot pricing: {str(e)}")
        return {"error": "Exception during API request", "message": str(e)}


async def check_dynadot_domain(domain: str, retries: int = 0) -> Dict:
    """
    Check availability and price for a single domain with retry logic.
    """
    if not DYNADOT_API_KEY:
        logger.error("Dynadot API key not configured")
        return {"available": False, "price": None, "error": "API key not configured"}

    logger.debug(f"Checking domain availability with Dynadot: {domain}")

    params = {
        "key": DYNADOT_API_KEY,
        "command": "search",
        "show_price": "1",
        "currency": "USD",
        "domain0": domain,
    }

    try:
        async with aiohttp.ClientSession() as session:
            logger.debug(f"Sending request to Dynadot API for domain: {domain}")
            async with session.get(
                DYNADOT_API_URL, params=params, timeout=10
            ) as response:
                if response.status == 200:
                    response_text = await response.text()
                    logger.debug(
                        f"Dynadot API response for {domain}: {response_text[:200]}..."
                    )

                    try:
                        data = json.loads(response_text)
                        search_results = data.get("SearchResponse", {}).get(
                            "SearchResults", []
                        )

                        if search_results and len(search_results) > 0:
                            result = search_results[0]
                            is_available = result.get("Available") == "yes"
                            price_string = result.get("Price")

                            price = None
                            if is_available and price_string:
                                # Extract the registration price from the string
                                price = extract_registration_price(price_string)
                                logger.debug(f"Extracted price for {domain}: {price}")

                            return {"available": is_available, "price": price}
                        else:
                            logger.warning(f"No search results found for {domain}")
                            return {
                                "available": False,
                                "price": None,
                                "error": "No response from API",
                            }
                    except json.JSONDecodeError as json_err:
                        logger.error(f"JSON decode error for {domain}: {str(json_err)}")
                        return {
                            "available": False,
                            "price": None,
                            "error": f"JSON decode error: {str(json_err)}",
                        }

                elif (
                    response.status == 429 and retries < MAX_RETRIES
                ):  # Too many requests (Rate limited)
                    logger.warning(
                        f"Rate limited for {domain}. Retrying in 3 seconds..."
                    )
                    await asyncio.sleep(3)
                    return await check_dynadot_domain(domain, retries + 1)

                else:
                    logger.error(f"Dynadot API error for {domain}: {response.status}")
                    return {
                        "available": False,
                        "price": None,
                        "error": f"API error {response.status}",
                    }

    except asyncio.TimeoutError:
        logger.error(f"Timeout error checking domain {domain}")
        if retries < MAX_RETRIES:
            logger.info(
                f"Retrying domain {domain} after timeout (retry {retries+1}/{MAX_RETRIES})"
            )
            await asyncio.sleep(3)  # Wait before retrying
            return await check_dynadot_domain(domain, retries + 1)
        return {"available": False, "price": None, "error": "Request timed out"}
    except Exception as e:
        logger.error(f"Error checking domain {domain}: {str(e)}")
        if retries < MAX_RETRIES:
            logger.info(
                f"Retrying domain {domain} after error (retry {retries+1}/{MAX_RETRIES})"
            )
            await asyncio.sleep(3)  # Wait before retrying
            return await check_dynadot_domain(domain, retries + 1)
        return {"available": False, "price": None, "error": f"Request failed: {str(e)}"}


async def check_dynadot_domains(domains: List[str]) -> Dict[str, Dict]:
    """
    Check multiple domains with Dynadot API

    Args:
        domains: List of full domain names to check (e.g. ["example.com", "example.net"])

    Returns:
        Dictionary mapping domain names to their availability info
    """
    if not domains:
        return {}

    logger.info(f"Checking {len(domains)} domains with Dynadot API")
    start_time = time.time()

    results = {}

    # Process domains in smaller batches to avoid overwhelming the API
    batch_size = 5
    for i in range(0, len(domains), batch_size):
        batch = domains[i : i + batch_size]
        logger.debug(f"Processing batch {i//batch_size + 1} with {len(batch)} domains")
        tasks = []

        for domain in batch:
            task = asyncio.create_task(check_dynadot_domain(domain))
            tasks.append((domain, task))

        # Wait for all tasks in the batch to complete
        for domain, task in tasks:
            try:
                domain_result = await task
                # Log the result for debugging
                logger.debug(f"Dynadot result for {domain}: {domain_result}")
                results[domain] = domain_result
            except Exception as e:
                logger.error(f"Error checking domain {domain} with Dynadot: {str(e)}")
                results[domain] = {
                    "available": False,
                    "price": None,
                    "error": f"Error: {str(e)}",
                }

        # Add a small delay between batches to avoid rate limiting
        if i + batch_size < len(domains):
            await asyncio.sleep(DELAY_BETWEEN_REQUESTS)

    elapsed_time = time.time() - start_time
    logger.info(
        f"Completed checking {len(domains)} domains with Dynadot in {elapsed_time:.2f} seconds"
    )

    # Log summary of results
    available_count = sum(
        1 for result in results.values() if result.get("available", False)
    )
    error_count = sum(
        1 for result in results.values() if "error" in result and result["error"]
    )
    logger.info(
        f"Dynadot results summary: {available_count} available, {error_count} errors, {len(results)} total"
    )

    return results
