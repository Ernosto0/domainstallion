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

    # Use regex to extract the registration price
    match = re.search(r"Registration Price: (\d+\.\d+)", price_string)
    if match:
        try:
            return float(match.group(1))
        except (ValueError, TypeError):
            logger.error(f"Failed to convert price to float: {match.group(1)}")
            return None

    return None


async def get_dynadot_pricing() -> Dict:
    """
    Fetch domain pricing from Dynadot API asynchronously.
    Returns a dictionary of TLDs with their pricing information.
    Caches results for 24 hours to reduce API calls.
    """
    global DYNADOT_PRICING_CACHE, CACHE_TIMESTAMP

    # Check if we have cached data that's still valid
    current_time = time.time()
    if DYNADOT_PRICING_CACHE and (current_time - CACHE_TIMESTAMP < CACHE_TTL):
        logger.debug("Using cached Dynadot pricing data")
        return DYNADOT_PRICING_CACHE

    logger.info("Fetching Dynadot pricing data...")
    logger.info(f"DYNADOT_API_KEY exists: {bool(DYNADOT_API_KEY)}")

    if not DYNADOT_API_KEY:
        logger.error("Dynadot API key not configured")
        return {"error": "API key not configured"}

    # Common TLDs to check for pricing
    common_tlds = ["com", "net", "org", "io", "ai", "app", "dev", "tech"]

    # Create a pricing dictionary
    pricing_data = {}

    try:
        async with aiohttp.ClientSession() as session:
            # Check pricing for common TLDs
            for tld in common_tlds:
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

            # Update cache
            DYNADOT_PRICING_CACHE = pricing_data
            CACHE_TIMESTAMP = current_time

            logger.info(
                f"Successfully cached pricing for {len(DYNADOT_PRICING_CACHE)} TLDs from Dynadot"
            )

            return DYNADOT_PRICING_CACHE

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
