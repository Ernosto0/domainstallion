import os
import json
import logging
import aiohttp
from typing import Tuple, Dict, Optional
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

logger = logging.getLogger(__name__)

# GoDaddy API configuration
GODADDY_API_KEY = os.getenv("GODADDY_API_KEY")
GODADDY_API_SECRET = os.getenv("GODADDY_API_SECRET")
GODADDY_API_URL = "https://api.ote-godaddy.com/v1/domains/available"

async def check_domain_availability(domain_name: str, extension: str) -> Tuple[bool, Optional[Dict]]:
    """
    Simplified domain availability checker that only uses GoDaddy API.
    Returns a tuple of (is_available, price_info)
    
    Args:
        domain_name: The domain name (without extension)
        extension: The domain extension (e.g., 'com', 'net')
        
    Returns:
        Tuple[bool, Optional[Dict]]: A tuple containing availability status and price info
    """
    full_domain = f"{domain_name}.{extension}"
    logger.info(f"Checking availability for domain: {full_domain}")
    
    try:
        if not GODADDY_API_KEY or not GODADDY_API_SECRET:
            logger.error("GoDaddy API credentials not configured")
            return False, None
        
        # Create aiohttp session
        async with aiohttp.ClientSession() as session:
            # Set up headers for GoDaddy API
            headers = {
                "Authorization": f"sso-key {GODADDY_API_KEY}:{GODADDY_API_SECRET}",
                "Content-Type": "application/json",
                "Accept": "application/json",
            }
            
            # Make the API request
            logger.debug(f"Making API request to GoDaddy for domain: {full_domain}")
            async with session.get(
                GODADDY_API_URL,
                params={"domain": full_domain, "checkType": "FAST"},
                headers=headers,
                timeout=10
            ) as response:
                if response.status == 200:
                    response_text = await response.text()
                    
                    try:
                        data = json.loads(response_text)
                        
                        # Extract availability and price information
                        is_available = data.get("available", False)
                        
                        if is_available:
                            # Format price information in a simple way
                            purchase_price = data.get("price", 0) / 1000000  # Convert from microdollars
                            price_info = {
                                "purchase": purchase_price,
                                "renewal": purchase_price  # Using same price for renewal for simplicity
                            }
                            
                            logger.info(f"Domain {full_domain} is available for ${purchase_price:.2f}")
                            return True, price_info
                        else:
                            logger.info(f"Domain {full_domain} is not available")
                            return False, None
                    
                    except json.JSONDecodeError:
                        logger.error(f"Invalid JSON response from GoDaddy API for {full_domain}")
                        return False, None
                
                elif response.status == 429:
                    logger.warning(f"Rate limit exceeded for GoDaddy API when checking {full_domain}")
                    return False, None
                
                else:
                    logger.error(f"GoDaddy API error for {full_domain}: Status {response.status}")
                    return False, None
    
    except Exception as e:
        logger.error(f"Error checking domain {full_domain}: {str(e)}")
        return False, None 