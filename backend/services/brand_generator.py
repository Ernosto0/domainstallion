from openai import OpenAI
import whois
import requests
import aiohttp
import asyncio
from typing import List, Dict
import os
from dotenv import load_dotenv
import logging
from concurrent.futures import ThreadPoolExecutor

# Configure logging
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

load_dotenv()

# Initialize OpenAI client
api_key = os.getenv("OPENAI_API_KEY")
godaddy_api_key = os.getenv("GODADDY_API_KEY")
godaddy_api_secret = os.getenv("GODADDY_API_SECRET")

# Common domain extensions to check
DOMAIN_EXTENSIONS = [
    "com",  # Most common, international
    "net",  # Network/tech related
    "org",  # Organizations
    "io",  # Tech startups
    "ai",  # AI/Tech companies
    "app",  # Applications
    "dev",  # Developer focused
    "tech",  # Technology focused
]

# Chunk size for concurrent API calls
CHUNK_SIZE = 4  # Adjust based on API rate limits

if not api_key:
    raise ValueError("OPENAI_API_KEY not found in environment variables")

# Create the client with minimal configuration
client = OpenAI(api_key=api_key)


class BrandGenerator:
    @staticmethod
    async def check_domain_price_async(
        session: aiohttp.ClientSession, domain: str
    ) -> Dict:
        """Check domain price using GoDaddy API asynchronously"""
        if not godaddy_api_key or not godaddy_api_secret:
            logger.warning("GoDaddy API credentials not found")
            return {
                "domain": domain,
                "available": True,
                "price": "Price check unavailable",
            }

        try:
            headers = {
                "Authorization": f"sso-key {godaddy_api_key}:{godaddy_api_secret}",
                "Content-Type": "application/json",
            }

            url = f" https://api.ote-godaddy.com/v1/domains/available?domain={domain}"
            logger.debug(f"Checking domain availability: {domain}")

            async with session.get(url, headers=headers) as response:
                if response.status == 200:
                    data = await response.json()
                    available = data.get("available", False)

                    if available:
                        price = data.get("price", 0)
                        formatted_price = f"${price/1000000:.2f}/yr"
                        logger.debug(
                            f"Domain {domain} is available at {formatted_price}"
                        )
                        return {
                            "domain": domain,
                            "available": True,
                            "price": formatted_price,
                        }
                    else:
                        logger.debug(f"Domain {domain} is taken")
                        return {"domain": domain, "available": False, "price": "Taken"}

                elif response.status == 429:
                    logger.warning("Rate limit exceeded for GoDaddy API")
                    return {
                        "domain": domain,
                        "available": True,
                        "price": "Rate limit exceeded",
                    }
                else:
                    logger.error(
                        f"GoDaddy API error: {response.status} - {await response.text()}"
                    )
                    return {
                        "domain": domain,
                        "available": True,
                        "price": "Price check failed",
                    }

        except Exception as e:
            logger.error(f"Error checking domain {domain}: {str(e)}")
            return {"domain": domain, "available": True, "price": "Check failed"}

    @staticmethod
    async def check_domains_batch(
        names: List[str], extensions: List[str]
    ) -> List[Dict]:
        """Check multiple domains concurrently in batches"""
        async with aiohttp.ClientSession() as session:
            all_results = []
            domains_to_check = [(name, ext) for name in names for ext in extensions]

            # Process domains in chunks to avoid overwhelming the API
            for i in range(0, len(domains_to_check), CHUNK_SIZE):
                chunk = domains_to_check[i : i + CHUNK_SIZE]
                tasks = []
                for name, ext in chunk:
                    domain = f"{name.lower()}.{ext}"
                    tasks.append(
                        BrandGenerator.check_domain_price_async(session, domain)
                    )

                # Wait for all tasks in the chunk to complete
                chunk_results = await asyncio.gather(*tasks)
                all_results.extend(chunk_results)

                # Add a small delay between chunks to avoid rate limiting
                if i + CHUNK_SIZE < len(domains_to_check):
                    await asyncio.sleep(0.5)

            return all_results

    @staticmethod
    async def generate_names(
        keywords: str, num_suggestions: int = 20
    ) -> List[Dict[str, any]]:
        logger.info(
            f"Starting name generation for keywords: {keywords}, requesting {num_suggestions} names"
        )

        system_prompt = """You are a brand name generator that creates exactly the requested number of names.
        You must return ONLY a numbered list of names, one per line, with no additional text or explanations.
        Format: 1. Name1\n2. Name2\n3. Name3\n..."""

        user_prompt = f"""Generate exactly {num_suggestions} unique brand names based on these keywords: {keywords}

        Requirements for EACH name:
        - Must be between 3-15 characters
        - Must work as a domain name (no spaces or special characters)
        - Must be unique and creative
        - Must be pronounceable
        - Must be memorable and brandable
        - Should be suitable for business use
        - Avoid numbers unless meaningful
        - No hyphens or special characters

        Respond with exactly {num_suggestions} names in this format:
        1. Name1
        2. Name2
        3. Name3
        (continue until {num_suggestions})"""

        try:
            logger.debug("Sending request to OpenAI API...")
            response = client.chat.completions.create(
                model="gpt-3.5-turbo",
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
                temperature=0.9,
                max_tokens=1000,
                presence_penalty=0.6,
                frequency_penalty=0.7,
                n=1,
            )

            logger.debug("Received response from OpenAI API")
            content = response.choices[0].message.content.strip()
            logger.debug(f"Raw content from API:\n{content}")

            # Extract names, removing the numbering
            generated_names = []
            for line in content.split("\n"):
                logger.debug(f"Processing line: {line}")
                name = line.strip()
                if name:
                    parts = name.split(". ", 1)
                    if len(parts) > 1:
                        name = parts[1].strip()
                        logger.debug(f"Extracted name: {name}")
                        if name and len(name) <= 15 and len(name) >= 3:
                            generated_names.append(name)
                            logger.debug(f"Added name to list: {name}")
                        else:
                            logger.debug(
                                f"Name rejected - length requirements not met: {name}"
                            )
                    else:
                        logger.debug(f"Line doesn't match expected format: {line}")

            # Check domain availability and prices concurrently
            domain_results = await BrandGenerator.check_domains_batch(
                generated_names, DOMAIN_EXTENSIONS
            )

            # Organize results by name
            results = []
            for name in generated_names:
                name_result = {"name": name, "domains": {}}

                # Find all domain results for this name
                for result in domain_results:
                    domain = result["domain"]
                    if domain.startswith(f"{name.lower()}."):
                        ext = domain.split(".")[-1]
                        name_result["domains"][ext] = {
                            "domain": domain,
                            "available": result["available"],
                            "price": result["price"],
                        }

                results.append(name_result)

            # Sort results by best availability and pricing across all domains
            def get_best_price(result):
                available_prices = []
                for domain_info in result["domains"].values():
                    if domain_info["available"]:
                        price = domain_info["price"]
                        try:
                            numeric_price = float(
                                price.replace("$", "").replace("/yr", "")
                            )
                            available_prices.append(numeric_price)
                        except (ValueError, AttributeError):
                            continue

                return min(available_prices) if available_prices else float("inf")

            # Sort by best available price
            results.sort(key=get_best_price)

            logger.info(f"Returning {len(results)} results")
            return results

        except Exception as e:
            logger.error(f"Error in generate_names: {str(e)}", exc_info=True)
            return []
