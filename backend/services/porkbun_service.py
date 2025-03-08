import os
import json
import logging
import aiohttp
from typing import Dict

logger = logging.getLogger(__name__)

# Porkbun API configuration
PORKBUN_API_KEY = os.getenv("PORKBUN_API_KEY")
PORKBUN_API_SECRET = os.getenv("PORKBUN_API_SECRET")

# API Endpoint for domain pricing
PORKBUN_PRICING_URL = "https://api.porkbun.com/api/json/v3/pricing/get"

# Cache for Porkbun pricing data
# Format: {tld: {registration: price, renewal: price, transfer: price}, ...}
PORKBUN_PRICING_CACHE = {}
CACHE_TIMESTAMP = 0
CACHE_TTL = 86400  # 24 hours in seconds


async def get_porkbun_pricing() -> Dict:
    """
    Fetch domain pricing from Porkbun API asynchronously.
    Returns a dictionary of TLDs with their pricing information.
    Caches results for 24 hours to reduce API calls.
    """
    global PORKBUN_PRICING_CACHE, CACHE_TIMESTAMP
    import time
    print("AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA")
    # Check if we have cached data that's still valid
    current_time = time.time()
    if PORKBUN_PRICING_CACHE and (current_time - CACHE_TIMESTAMP < CACHE_TTL):
        logger.debug("Using cached Porkbun pricing data")
        return PORKBUN_PRICING_CACHE

    logger.info("Fetching Porkbun pricing data...")
    logger.info(f"PORKBUN_API_KEY exists: {bool(PORKBUN_API_KEY)}")
    logger.info(f"PORKBUN_API_SECRET exists: {bool(PORKBUN_API_SECRET)}")

    if not PORKBUN_API_KEY or not PORKBUN_API_SECRET:
        logger.error("Porkbun API credentials not configured")
        return {"error": "API credentials not configured"}

    data = {"apikey": PORKBUN_API_KEY, "secretapikey": PORKBUN_API_SECRET}
    logger.info(f"Sending request to Porkbun API: {PORKBUN_PRICING_URL}")

    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(
                PORKBUN_PRICING_URL, json=data, timeout=30
            ) as response:
                logger.info(f"Porkbun API response status: {response.status}")

                if response.status == 200:
                    response_text = await response.text()
                    logger.debug(
                        f"Porkbun API response: {response_text[:200]}..."
                    )  # Log first 200 chars

                    try:
                        pricing_data = json.loads(response_text)
                        logger.info(
                            f"Porkbun API response status: {pricing_data.get('status')}"
                        )

                        if pricing_data.get("status") == "SUCCESS":
                            # Update cache
                            PORKBUN_PRICING_CACHE = pricing_data.get("pricing", {})
                            CACHE_TIMESTAMP = current_time

                            # Only log total number of TLDs
                            logger.info(
                                f"Successfully cached pricing for {len(PORKBUN_PRICING_CACHE)} TLDs from Porkbun"
                            )

                            # Log common TLD prices for reference
                            common_tlds = ["com", "net", "org", "io"]
                            for tld in common_tlds:
                                if tld in PORKBUN_PRICING_CACHE:
                                    prices = PORKBUN_PRICING_CACHE.get(tld, {})
                                    logger.info(
                                        f".{tld} - Registration: ${prices.get('registration')}, Renewal: ${prices.get('renewal')}"
                                    )

                            # Log a sample of the pricing data structure
                            sample_tld = (
                                next(iter(PORKBUN_PRICING_CACHE))
                                if PORKBUN_PRICING_CACHE
                                else None
                            )
                            if sample_tld:
                                logger.info(
                                    f"Sample pricing data structure for .{sample_tld}: {PORKBUN_PRICING_CACHE[sample_tld]}"
                                )

                            logger.info("Porkbun pricing data retrieved successfully")
                            return PORKBUN_PRICING_CACHE
                        else:
                            error_msg = pricing_data.get("message", "Unknown error")
                            logger.error(f"Porkbun API error: {error_msg}")
                            return {"error": "API request failed", "message": error_msg}

                    except json.JSONDecodeError as json_err:
                        logger.error(
                            f"JSON decode error for Porkbun API: {str(json_err)}"
                        )
                        return {
                            "error": "Invalid API response",
                            "message": str(json_err),
                        }

                else:
                    error_text = await response.text()
                    logger.error(
                        f"Porkbun API request failed with status {response.status}: {error_text}"
                    )
                    return {
                        "error": f"Failed to fetch data: {response.status}",
                        "message": error_text,
                    }

    except Exception as e:
        logger.error(f"Error fetching Porkbun pricing: {str(e)}")
        return {"error": "Exception during API request", "message": str(e)}
