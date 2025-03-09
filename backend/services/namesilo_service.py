import os
import json
import logging
import aiohttp
import time
from typing import Dict

logger = logging.getLogger(__name__)

# Namesilo API configuration
NAMESILO_API_KEY = os.getenv("NAMESILO_API_KEY")
NAMESILO_API_URL = "https://www.namesilo.com/api/getPrices"

# Cache for Namesilo pricing data
# Format: {tld: {registration: price, renewal: price, transfer: price}, ...}
NAMESILO_PRICING_CACHE = {}
CACHE_TIMESTAMP = 0
CACHE_TTL = 86400  # 24 hours in seconds


async def get_namesilo_pricing() -> Dict:
    """
    Fetch domain pricing from Namesilo API asynchronously.
    Returns a dictionary of TLDs with their pricing information.
    Caches results for 24 hours to reduce API calls.
    """
    global NAMESILO_PRICING_CACHE, CACHE_TIMESTAMP

    # Check if we have cached data that's still valid
    current_time = time.time()
    if NAMESILO_PRICING_CACHE and (current_time - CACHE_TIMESTAMP < CACHE_TTL):
        logger.debug("Using cached Namesilo pricing data")
        return NAMESILO_PRICING_CACHE

    logger.info("Fetching Namesilo pricing data...")
    logger.info(f"NAMESILO_API_KEY exists: {bool(NAMESILO_API_KEY)}")

    if not NAMESILO_API_KEY:
        logger.error("Namesilo API key not configured")
        return {"error": "API key not configured"}

    params = {"version": "1", "type": "json", "key": NAMESILO_API_KEY}

    try:
        async with aiohttp.ClientSession() as session:
            logger.debug(f"Sending request to Namesilo API: {NAMESILO_API_URL}")
            async with session.get(
                NAMESILO_API_URL, params=params, timeout=30
            ) as response:
                logger.info(f"Namesilo API response status: {response.status}")

                if response.status == 200:
                    response_text = await response.text()
                    logger.debug(
                        f"Namesilo API response: {response_text[:200]}..."
                    )  # Log first 200 chars

                    try:
                        data = json.loads(response_text)

                        if data.get("reply", {}).get("code") == 300:
                            # Extract pricing data
                            pricing_data = {}
                            reply_data = data.get("reply", {})

                            # Process each TLD in the response
                            for tld, details in reply_data.items():
                                if isinstance(
                                    details, dict
                                ):  # Ignore non-TLD keys like 'code' and 'detail'
                                    pricing_data[tld] = {
                                        "registration": details.get(
                                            "registration", "N/A"
                                        ),
                                        "renewal": details.get("renew", "N/A"),
                                        "transfer": details.get("transfer", "N/A"),
                                    }

                            # Update cache
                            NAMESILO_PRICING_CACHE = pricing_data
                            CACHE_TIMESTAMP = current_time

                            # Log common TLD prices for reference
                            common_tlds = ["com", "net", "org", "io"]
                            for tld in common_tlds:
                                if tld in NAMESILO_PRICING_CACHE:
                                    prices = NAMESILO_PRICING_CACHE.get(tld, {})
                                    logger.info(
                                        f".{tld} - Registration: ${prices.get('registration')}, Renewal: ${prices.get('renewal')}"
                                    )

                            logger.info(
                                f"Successfully cached pricing for {len(NAMESILO_PRICING_CACHE)} TLDs from Namesilo"
                            )
                            return NAMESILO_PRICING_CACHE
                        else:
                            error_msg = data.get("reply", {}).get(
                                "detail", "Unknown error"
                            )
                            logger.error(f"Namesilo API error: {error_msg}")
                            return {"error": "API request failed", "message": error_msg}

                    except json.JSONDecodeError as json_err:
                        logger.error(
                            f"JSON decode error for Namesilo API: {str(json_err)}"
                        )
                        return {
                            "error": "Invalid API response",
                            "message": str(json_err),
                        }

                else:
                    error_text = await response.text()
                    logger.error(
                        f"Namesilo API request failed with status {response.status}: {error_text}"
                    )
                    return {
                        "error": f"Failed to fetch data: {response.status}",
                        "message": error_text,
                    }

    except Exception as e:
        logger.error(f"Error fetching Namesilo pricing: {str(e)}")
        return {"error": "Exception during API request", "message": str(e)}
