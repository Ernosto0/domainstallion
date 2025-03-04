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
from .domain_scorer import DomainScorer

# Configure logging
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)
handler = logging.StreamHandler()
formatter = logging.Formatter("%(asctime)s - %(name)s - %(levelname)s - %(message)s")
handler.setFormatter(formatter)
logger.addHandler(handler)

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
    def __init__(self):
        self.client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
        self.godaddy_api_key = os.getenv("GODADDY_API_KEY")
        self.godaddy_api_secret = os.getenv("GODADDY_API_SECRET")
        self.domain_scorer = DomainScorer()

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

            url = f"https://api.ote-godaddy.com/v1/domains/available?domain={domain}"
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

    async def check_domain_availability(self, domain):
        url = f"https://api.ote-godaddy.com/v1/domains/available?domain={domain}"
        headers = {
            "Authorization": f"sso-key {self.godaddy_api_key}:{self.godaddy_api_secret}",
            "accept": "application/json",
        }

        logger.debug(f"Making GoDaddy API request for domain: {domain}")
        logger.debug(f"Using URL: {url}")

        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(url, headers=headers) as response:
                    logger.debug(f"GoDaddy API response status: {response.status}")
                    data = await response.json()
                    logger.debug(f"GoDaddy API response data: {data}")

                    if response.status == 200:
                        return {
                            "available": data.get("available", False),
                            "price": (
                                data.get("price", 0) / 1000000
                                if data.get("price")
                                else None
                            ),
                            "error": None,
                        }
                    else:
                        return {
                            "available": False,
                            "price": None,
                            "error": data.get("message", "API Error"),
                        }
        except Exception as e:
            logger.error(f"Error in GoDaddy API call: {str(e)}")
            return {"available": False, "price": None, "error": str(e)}

    async def generate_names(
        self,
        keywords,
        style="neutral",
        num_suggestions=20,
        min_length=3,
        max_length=15,
        include_word=None,
    ):
        """
        Generate brand names based on keywords and desired style.

        Args:
            keywords (str): Keywords to base the brand names on
            style (str): Desired style - 'short', 'playful', 'serious', or 'techy'
            num_suggestions (int): Number of suggestions to generate
            min_length (int): Minimum length for generated names (default: 3)
            max_length (int): Maximum length for generated names (default: 15)
            include_word (str, optional): A specific word to include in the generated names
        """
        # Style-specific guidelines
        style_guidelines = {
            "short": "Names should be concise, preferably 3-6 characters.",
            "playful": "Names should be fun, memorable, and potentially use wordplay or rhyming.",
            "serious": "Names should be professional, trustworthy, and business-oriented.",
            "techy": "Names should sound innovative, modern, and tech-savvy, potentially using tech-related suffixes.",
        }

        # Get style-specific guidelines or use neutral if style not specified
        style_guide = style_guidelines.get(
            style.lower(), "Names should be balanced and versatile."
        )
        logger.debug(f"Style guide: {style_guide}")

        
        # Build the word inclusion part of the prompt
        word_inclusion_prefix = (
            f"\nIMPORTANT: Each generated name MUST include the word '{include_word}'. The word should be incorporated naturally into the name, either as a prefix, suffix, or part of a compound word."
            if include_word
            else ""
        )

        word_inclusion = (
            f"8. Must include the word '{include_word}' in each name (can be part of a larger word)"
            if include_word
            else ""
        )

        prompt = f"""{word_inclusion_prefix}Generate {num_suggestions} unique and creative brand names based on these keywords: {keywords}.
        Style requirement: {style_guide}
        
        Rules:
        1. Names MUST be between {min_length}-{max_length} characters
        2. Should be easy to pronounce
        3. Can include real words or made-up words
        4. Can include double letters for style (like Google)
        5. Return only the names, one per line
        6. Do not include numbers or dots in the names
        7. Ensure names match the requested style: {style}
        {word_inclusion}
        
        Example format:
        BrandName1
        BrandName2
        (just the names, one per line)"""

        try:
            logger.debug("Starting OpenAI API call")
            logger.debug(
                f"Using parameters - min_length: {min_length}, max_length: {max_length}, include_word: {include_word}"
            )
            response = self.client.chat.completions.create(
                model="gpt-3.5-turbo",
                messages=[{"role": "user", "content": prompt}],
                temperature=0.7,
                max_tokens=200,
            )
            logger.debug(
                f"OpenAI API response received: {response.choices[0].message.content}"
            )

            # Clean up brand names
            brand_names = []
            raw_lines = response.choices[0].message.content.strip().split("\n")
            logger.debug(f"Processing {len(raw_lines)} raw lines")

            for line in raw_lines:
                # Remove leading/trailing whitespace
                name = line.strip()
                logger.debug(f"Processing line: '{line}' -> '{name}'")

                # Remove numbered list format if present
                if ". " in name:
                    parts = name.split(". ", 1)
                    if len(parts) == 2 and parts[0].strip().isdigit():
                        name = parts[1].strip()
                        logger.debug(f"Removed numbering: '{line}' -> '{name}'")

                # Skip empty lines
                if not name:
                    logger.debug("Skipping empty line")
                    continue

                # Skip if name contains numbers
                if any(c.isdigit() for c in name):
                    logger.debug(f"Skipping name with numbers: {name}")
                    continue

                # Validate length constraints
                if not (min_length <= len(name) <= max_length):
                    logger.debug(
                        f"Skipping name due to length: {name} (length: {len(name)})"
                    )
                    continue

                # Only validate word inclusion if a word is specified and it's not empty
                if (
                    include_word
                    and include_word.strip()
                    and include_word.lower().strip() not in name.lower()
                ):
                    logger.debug(
                        f"Skipping name missing required word '{include_word}': {name}"
                    )
                    continue

                logger.debug(f"Adding valid name: {name}")
                brand_names.append(name)

            logger.debug(
                f"Final cleaned brand names ({len(brand_names)}): {brand_names}"
            )

            if not brand_names:
                logger.error("No valid brand names generated")
                return []

            results = []
            extensions = ["com", "io", "ai", "app", "net"]

            # Create all domain combinations
            domain_checks = []
            for name in brand_names:
                for ext in extensions:
                    domain_checks.append((name, ext))
            logger.debug(f"Created {len(domain_checks)} domain combinations to check")

            async with aiohttp.ClientSession(
                timeout=aiohttp.ClientTimeout(total=30)
            ) as session:
                # Function to check domain and get score
                async def check_domain_and_score(name_ext_tuple):
                    try:
                        name, ext = name_ext_tuple
                        domain = f"{name}.{ext}"
                        url = f"https://api.ote-godaddy.com/v1/domains/available?domain={domain}"
                        headers = {
                            "Authorization": f"sso-key {self.godaddy_api_key}:{self.godaddy_api_secret}",
                            "accept": "application/json",
                        }

                        logger.debug(f"Starting domain check for: {domain}")
                        async with session.get(
                            url, headers=headers, timeout=10
                        ) as response:
                            data = await response.json()
                            logger.debug(f"GoDaddy API response for {domain}: {data}")

                            availability = {
                                "available": data.get("available", False),
                                "price": (
                                    data.get("price", 0) / 1000000
                                    if data.get("price")
                                    else None
                                ),
                                "error": (
                                    None
                                    if response.status == 200
                                    else data.get("message", "API Error")
                                ),
                            }

                        try:
                            domain_score = self.domain_scorer.calculate_total_score(
                                name, ext
                            )
                            logger.debug(
                                f"Domain score calculated for {domain}: {domain_score}"
                            )
                            logger.debug(f"Raw score object: {domain_score}")
                            logger.debug(
                                f"Total score: {domain_score.get('total_score')}"
                            )
                            logger.debug(
                                f"Score details: {domain_score.get('details')}"
                            )

                            # Validate score structure
                            if not isinstance(
                                domain_score.get("total_score"), (int, float)
                            ):
                                logger.error(
                                    f"Invalid total_score type for {domain}: {type(domain_score.get('total_score'))}"
                                )

                            for key, detail in domain_score.get("details", {}).items():
                                if not isinstance(detail.get("score"), (int, float)):
                                    logger.error(
                                        f"Invalid {key} score type for {domain}: {type(detail.get('score'))}"
                                    )
                        except Exception as score_error:
                            logger.error(
                                f"Error calculating score for {domain}: {str(score_error)}"
                            )
                            domain_score = {
                                "total_score": 0,
                                "details": {
                                    "length": {
                                        "score": 0,
                                        "description": "Error calculating length score",
                                    },
                                    "dictionary": {
                                        "score": 0,
                                        "description": "Error calculating dictionary score",
                                    },
                                    "pronounceability": {
                                        "score": 0,
                                        "description": "Error calculating pronounceability score",
                                    },
                                    "repetition": {
                                        "score": 0,
                                        "description": "Error calculating repetition score",
                                    },
                                    "tld": {
                                        "score": 0,
                                        "description": "Error calculating TLD score",
                                    },
                                },
                            }

                        # Ensure the score object has the correct structure
                        if (
                            not isinstance(domain_score, dict)
                            or "total_score" not in domain_score
                            or "details" not in domain_score
                        ):
                            logger.error(
                                f"Invalid score structure for {domain}: {domain_score}"
                            )
                            domain_score = {
                                "total_score": 0,
                                "details": {
                                    "length": {
                                        "score": 0,
                                        "description": "Invalid score structure",
                                    },
                                    "dictionary": {
                                        "score": 0,
                                        "description": "Invalid score structure",
                                    },
                                    "pronounceability": {
                                        "score": 0,
                                        "description": "Invalid score structure",
                                    },
                                    "repetition": {
                                        "score": 0,
                                        "description": "Invalid score structure",
                                    },
                                    "tld": {
                                        "score": 0,
                                        "description": "Invalid score structure",
                                    },
                                },
                            }

                        return {
                            "name": name,
                            "ext": ext,
                            "domain": domain,
                            "available": availability["available"],
                            "price": (
                                f"${availability['price']}"
                                if availability["available"] and availability["price"]
                                else "N/A"
                            ),
                            "score": domain_score,
                            "error": availability.get("error"),
                        }
                    except Exception as e:
                        logger.error(f"Error checking domain {name}.{ext}: {str(e)}")
                        return {
                            "name": name,
                            "ext": ext,
                            "domain": f"{name}.{ext}",
                            "available": False,
                            "price": "N/A",
                            "score": {
                                "total_score": 0,
                                "details": {
                                    "length": {
                                        "score": 0,
                                        "description": "Error checking domain",
                                    },
                                    "dictionary": {
                                        "score": 0,
                                        "description": "Error checking domain",
                                    },
                                    "pronounceability": {
                                        "score": 0,
                                        "description": "Error checking domain",
                                    },
                                    "repetition": {
                                        "score": 0,
                                        "description": "Error checking domain",
                                    },
                                    "tld": {
                                        "score": 0,
                                        "description": "Error checking domain",
                                    },
                                },
                            },
                            "error": str(e),
                        }

                # Process domains in chunks
                results = []
                chunk_size = 5
                for i in range(0, len(domain_checks), chunk_size):
                    try:
                        chunk = domain_checks[i : i + chunk_size]
                        tasks = [check_domain_and_score(item) for item in chunk]
                        chunk_results = await asyncio.gather(
                            *tasks, return_exceptions=True
                        )
                        valid_results = []
                        for result in chunk_results:
                            if isinstance(result, Exception):
                                logger.error(f"Task error: {str(result)}")
                            else:
                                valid_results.append(result)
                        results.extend(valid_results)

                        if i + chunk_size < len(domain_checks):
                            await asyncio.sleep(0.1)
                    except Exception as chunk_error:
                        logger.error(f"Error processing chunk {i}: {str(chunk_error)}")

                # Organize results by brand name
                name_results = {}
                for result in results:
                    try:
                        name = result["name"]
                        if name not in name_results:
                            name_results[name] = {"name": name, "domains": {}}
                        name_results[name]["domains"][result["ext"]] = {
                            "domain": result["domain"],
                            "available": result["available"],
                            "price": result["price"],
                            "score": result["score"],
                            "error": result["error"],
                        }
                        # Log the score data being added
                        logger.debug(
                            f"Adding score for {result['domain']}: {result['score']}"
                        )
                    except Exception as result_error:
                        logger.error(f"Error processing result: {str(result_error)}")

                logger.debug(f"Final results count: {len(name_results)}")
                # Log a sample of the final data structure
                if name_results:
                    sample_name = next(iter(name_results))
                    logger.debug(
                        f"Sample result structure for {sample_name}: {name_results[sample_name]}"
                    )
                return list(name_results.values())

        except Exception as e:
            logger.error(f"Error in generate_names: {str(e)}", exc_info=True)
            raise
