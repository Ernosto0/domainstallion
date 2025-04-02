from openai import OpenAI
import openai
import whois
import requests
import aiohttp
import asyncio
from typing import List, Dict, Optional
import os
from dotenv import load_dotenv
import logging
from concurrent.futures import ThreadPoolExecutor
from .domain_scorer import DomainScorer
from fastapi import HTTPException, status
from .domain_checker import check_multiple_domains
import random
import string
import re
from collections import Counter

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
CHUNK_SIZE = 20  

if not api_key:
    raise ValueError("OPENAI_API_KEY not found in environment variables")

# Create the client with minimal configuration
openai.api_key = api_key


# Custom exceptions
class BrandGeneratorError(Exception):
    def __init__(
        self,
        message: str,
        error_code: str,
        status_code: int = 500,
        details: Optional[Dict] = None,
    ):
        self.message = message
        self.error_code = error_code
        self.status_code = status_code
        self.details = details or {}
        super().__init__(self.message)


class APIKeyError(BrandGeneratorError):
    def __init__(self, service: str):
        super().__init__(
            message=f"{service} API key not found",
            error_code="API_KEY_MISSING",
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            details={"service": service},
        )


class DomainCheckError(BrandGeneratorError):
    def __init__(self, domain: str, original_error: str):
        super().__init__(
            message=f"Failed to check domain {domain}",
            error_code="DOMAIN_CHECK_FAILED",
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            details={"domain": domain, "original_error": str(original_error)},
        )


class NameGenerationError(BrandGeneratorError):
    def __init__(self, keywords: str, original_error: str):
        super().__init__(
            message=f"Failed to generate names for keywords: {keywords}",
            error_code="NAME_GENERATION_FAILED",
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            details={"keywords": keywords, "original_error": str(original_error)},
        )


class BrandGenerator:
    def __init__(self):
        self.client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
        if not self.client.api_key:
            raise APIKeyError("OpenAI")

        self.domain_scorer = DomainScorer()
        
        # Common word patterns to avoid in domain names
        self.common_patterns = [
            r'^app$', r'^my', r'^the', r'^get', r'^go', r'^use', 
            r'^pro$', r'^live$', r'^best', r'^top', r'^smart', 
            r'^easy', r'^simple', r'^quick', r'^fast', r'^instant',
            r'^online$', r'^web$', r'^tech$', r'^digital$'
        ]

    def _is_too_common(self, name):
        """Check if a name contains patterns that are likely to be taken domains."""
        name_lower = name.lower()
        
        # Check common patterns
        for pattern in self.common_patterns:
            if re.search(pattern, name_lower):
                return True
                
        # Check if the name is too short and simple (likely taken)
        if len(name) <= 4 and name.isalpha() and name.islower():
            return True
            
        return False
    
    def _add_uniqueness(self, names, count=10):
        """Add uniqueness to a subset of names by applying creative transformations."""
        if not names:
            return []
            
        unique_names = []
        original_names = names.copy()  # Keep the original list intact
        
        # Take a subset of names to transform (but at least 1)
        subset_count = min(max(1, count), len(names))
        subset = random.sample(names, subset_count)
        
        for name in subset:
            # Apply 1-3 random transformations
            transformations = random.randint(1, 3)
            transformed_name = name
            
            for _ in range(transformations):
                # Choose a random transformation
                transform_type = random.choice([
                    'swap_letters', 'vowel_change', 'add_prefix', 
                    'add_suffix', 'double_letter', 'remove_vowel'
                ])
                
                if transform_type == 'swap_letters' and len(transformed_name) > 3:
                    # Swap two adjacent letters
                    pos = random.randint(0, len(transformed_name) - 2)
                    chars = list(transformed_name)
                    chars[pos], chars[pos + 1] = chars[pos + 1], chars[pos]
                    transformed_name = ''.join(chars)
                
                elif transform_type == 'vowel_change':
                    # Replace a vowel with another vowel or 'y'
                    vowels = 'aeiou'
                    replacements = 'aeiouy'
                    chars = list(transformed_name)
                    
                    # Find vowel positions
                    vowel_positions = [i for i, char in enumerate(chars) if char.lower() in vowels]
                    if vowel_positions:
                        pos = random.choice(vowel_positions)
                        original_case = chars[pos].isupper()
                        new_vowel = random.choice(replacements)
                        chars[pos] = new_vowel.upper() if original_case else new_vowel
                        transformed_name = ''.join(chars)
                
                elif transform_type == 'add_prefix':
                    # Add a short prefix
                    prefixes = ['e', 'i', 'x', 'z', 'v', 'neo', 'ex', 'fy', 'my', 'nu', 'zo', 'zi', 'vi']
                    prefix = random.choice(prefixes)
                    transformed_name = prefix + transformed_name
                
                elif transform_type == 'add_suffix':
                    # Add a short suffix
                    suffixes = ['ly', 'io', 'ify', 'ity', 'ify', 'ium', 'ble', 'ize', 'sy', 'zy', 'er']
                    suffix = random.choice(suffixes)
                    transformed_name = transformed_name + suffix
                
                elif transform_type == 'double_letter':
                    # Double a random letter
                    if len(transformed_name) > 2:
                        pos = random.randint(0, len(transformed_name) - 1)
                        transformed_name = transformed_name[:pos] + transformed_name[pos] + transformed_name[pos:]
                
                elif transform_type == 'remove_vowel':
                    # Remove a vowel if it won't harm pronounceability
                    vowels = 'aeiou'
                    chars = list(transformed_name)
                    
                    # Find vowel positions (not first or last letter)
                    vowel_positions = [i for i, char in enumerate(chars) 
                                     if i > 0 and i < len(chars)-1 and char.lower() in vowels]
                    
                    # Don't remove a vowel if it would create a 3+ consonant cluster
                    safe_positions = []
                    for pos in vowel_positions:
                        if not (chars[pos-1].lower() not in vowels and chars[pos+1].lower() not in vowels):
                            safe_positions.append(pos)
                    
                    if safe_positions:
                        pos = random.choice(safe_positions)
                        transformed_name = transformed_name[:pos] + transformed_name[pos+1:]
            
            # Only add if the transformation actually changed the name and meets length requirements
            if (transformed_name not in original_names and 
                transformed_name not in unique_names and 
                3 <= len(transformed_name) <= 15):
                unique_names.append(transformed_name)
        
        return unique_names

    async def generate_names(
        self,
        keywords,
        style="neutral",
        num_suggestions=20,  
        min_length=3,
        max_length=15,
        include_word=None,
        similar_to=None,
        extensions=None,  # New parameter for custom extensions
    ):
        try:
            # Validate inputs
            if not keywords:
                raise BrandGeneratorError(
                    message="Keywords cannot be empty",
                    error_code="INVALID_KEYWORDS",
                    status_code=status.HTTP_400_BAD_REQUEST,
                )

            if style not in ["short", "playful", "serious", "techy", "neutral", "creative"]:
                raise BrandGeneratorError(
                    message="Invalid style specified",
                    error_code="INVALID_STYLE",
                    status_code=status.HTTP_400_BAD_REQUEST,
                    details={
                        "valid_styles": [
                            "short",
                            "playful",
                            "serious",
                            "techy",
                            "neutral",
                            "creative"
                        ]
                    },
                )

            if min_length > max_length:
                raise BrandGeneratorError(
                    message="Minimum length cannot be greater than maximum length",
                    error_code="INVALID_LENGTH_RANGE",
                    status_code=status.HTTP_400_BAD_REQUEST,
                    details={"min_length": min_length, "max_length": max_length},
                )
                
            # Validate extensions
            if not extensions or not isinstance(extensions, list) or len(extensions) == 0:
                logger.debug("No extensions provided, using defaults")
                # Default extensions if none provided
                extensions = ["com", "io", "ai", "app", "net"]
            else:
                logger.debug(f"Using custom extensions: {extensions}")
                # Validate the extensions are in our supported list
                valid_extensions = set(DOMAIN_EXTENSIONS)
                extensions = [ext for ext in extensions if ext in valid_extensions]
                
                if not extensions:
                    logger.warning("No valid extensions after filtering, using defaults")
                    extensions = ["com", "io", "ai", "app", "net"]

            # Style-specific guidelines
            style_guidelines = {
                "short": "Names should be concise, preferably 6-9 characters.",
                "playful": "Names should be fun, memorable, and potentially use wordplay or rhyming.",
                "serious": "Names should be professional, trustworthy, and business-oriented.",
                "techy": "Names should sound innovative, modern, and tech-savvy, potentially using tech-related suffixes.",
                "creative": "Names should be highly unique, using unexpected word combinations, letter substitutions, or invented terms."
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

            # Build the similar_to part of the prompt
            similar_to_prefix = (
                f"\nIMPORTANT: Generate names that are similar in style, sound, or concept to '{similar_to}'. Use similar patterns, suffixes, or word structures, but make them unique enough to be distinctive."
                if similar_to
                else ""
            )
            
            
            similar_to_rule = (
                f"11. Generate names with similar style, phonetics, or concept to '{similar_to}', but distinct enough to be unique"
                if similar_to
                else ""
            )

            creativity_boost = """
            IMPORTANT CREATIVITY GUIDELINES:
            - Create truly UNIQUE and DISTINCTIVE names that are unlikely to be taken
            - Use unexpected letter combinations that are still pronounceable
            - Consider partial word blends and creative misspellings 
            - Add distinctive prefixes or suffixes to common words
            - Invent entirely new words that evoke the feeling of the keywords
            - Combine words in surprising ways
            - Use alternative spellings (replace 'c' with 'k', 'i' with 'y', etc.) 
            - Create compound words from partial words
            - DO NOT use common dictionary words as standalone names
            """

            prompt = f"""{word_inclusion_prefix}{similar_to_prefix}Generate {num_suggestions} unique and creative brand names based on these keywords: {keywords}.
            Style requirement: {style_guide}
            
            {creativity_boost}
            
            Rules:
            1. Names MUST be between {min_length}-{max_length} characters
            2. Should be easy to pronounce
            3. Can include real words or made-up words
            4. Can include double letters for style (like Google)
            5. Return only the names, one per line
            6. Do not include numbers or dots in the names
            7. Ensure names match the requested style: {style}
            {word_inclusion}
            {similar_to_rule}
            9. AVOID using any common words as standalone names, they are likely taken
            10. CREATE highly distinctive names, not obvious combinations of the keywords
            
            Example format:
            BrandName1
            BrandName2
            (just the names, one per line)"""

            try:
                logger.debug("Starting OpenAI API call")
                logger.debug(
                    f"Using parameters - min_length: {min_length}, max_length: {max_length}, include_word: {include_word}, similar_to: {similar_to}"
                )
                response = self.client.chat.completions.create(
                    model="gpt-3.5-turbo",  # Using GPT-4o for more creative results
                    messages=[{"role": "user", "content": prompt}],
                    temperature=0.9,
                    max_tokens=300,
                    presence_penalty=0.6,
                    frequency_penalty=0.8
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
                    
                    # Skip if name is likely to be already taken
                    if self._is_too_common(name):
                        logger.debug(f"Skipping common name pattern: {name}")
                        continue

                    logger.debug(f"Adding valid name: {name}")
                    brand_names.append(name)
                
                # Add some uniquely transformed names for more creativity
                unique_names = self._add_uniqueness(brand_names, count=min(10, num_suggestions//3))
                brand_names.extend(unique_names)
                logger.debug(f"Added {len(unique_names)} uniquely transformed names")

                logger.debug(
                    f"Final cleaned brand names ({len(brand_names)}): {brand_names}"
                )

                if not brand_names:
                    logger.error("No valid brand names generated")
                    return []

                results = []
                # Use the extensions provided by the user
                logger.info(f"Checking domains with extensions: {extensions}")

                # Create all domain combinations
                domain_checks = []
                for name in brand_names:
                    for ext in extensions:
                        domain_checks.append((name, ext))
                logger.debug(
                    f"Created {len(domain_checks)} domain combinations to check"
                )

                async with aiohttp.ClientSession(
                    timeout=aiohttp.ClientTimeout(total=20),
                    connector=aiohttp.TCPConnector(
                        limit=20, ssl=False
                    ),  # Increased connection limit
                ) as session:
                    # Pre-calculate domain scores for all names to avoid redundant calculations
                    domain_scores_cache = {}
                    for name in brand_names:
                        for ext in extensions:
                            key = f"{name}:{ext}"
                            try:
                                domain_scores_cache[key] = (
                                    self.domain_scorer.calculate_total_score(name, ext)
                                )
                            except Exception as score_error:
                                logger.error(
                                    f"Error pre-calculating score for {name}.{ext}: {str(score_error)}"
                                )
                                domain_scores_cache[key] = {
                                    "total_score": 0,
                                    "details": {
                                        "length": {
                                            "score": 0,
                                            "description": "Error calculating score",
                                        },
                                        "dictionary": {
                                            "score": 0,
                                            "description": "Error calculating score",
                                        },
                                        "pronounceability": {
                                            "score": 0,
                                            "description": "Error calculating score",
                                        },
                                        "repetition": {
                                            "score": 0,
                                            "description": "Error calculating score",
                                        },
                                        "tld": {
                                            "score": 0,
                                            "description": "Error calculating score",
                                        },
                                    },
                                }

                    # Process domains in chunks using bulk API
                    results = []
                    chunk_size = 20  # Increased from 10 to 20 for better performance

                    # Process domains in chunks
                    for i in range(0, len(domain_checks), chunk_size):
                        try:
                            chunk = domain_checks[i : i + chunk_size]

                            # Prepare domains for bulk check
                            domains_to_check = [f"{name}.{ext}" for name, ext in chunk]

                            # Use domain checker module with bulk API
                            from .domain_checker import check_multiple_domains

                            # Use the improved domain checker that handles errors internally
                            bulk_results = await check_multiple_domains(
                                domains_to_check
                            )

                            # Process results
                            chunk_results = []
                            for name, ext in chunk:
                                domain = f"{name}.{ext}"

                                # Get domain info from results, or create a default if missing
                                domain_info = bulk_results.get(domain, {})
                                if not domain_info:
                                    logger.warning(
                                        f"No domain info for {domain}, using default"
                                    )
                                    domain_info = {
                                        "available": False,
                                        "price_info": None,
                                        "error": "No data returned",
                                    }

                                # Get availability info
                                is_available = domain_info.get("available", False)
                                price_info = domain_info.get("price_info")
                                error = domain_info.get("error")

                                # Get provider prices if available
                                providers = domain_info.get("providers", {})
                                if is_available:
                                    logger.info(
                                        f"Provider information for {domain}: {providers}"
                                    )

                                # Get score from cache
                                score_key = f"{name}:{ext}"
                                domain_score = domain_scores_cache.get(score_key)
                                if not domain_score:
                                    logger.warning(
                                        f"No score for {domain}, using default"
                                    )
                                    domain_score = {
                                        "total_score": 50,  # Default middle score
                                        "details": {
                                            "length": {
                                                "score": 50,
                                                "description": "Default score",
                                            },
                                            "dictionary": {
                                                "score": 50,
                                                "description": "Default score",
                                            },
                                            "pronounceability": {
                                                "score": 50,
                                                "description": "Default score",
                                            },
                                            "repetition": {
                                                "score": 50,
                                                "description": "Default score",
                                            },
                                            "tld": {
                                                "score": 50,
                                                "description": "Default score",
                                            },
                                        },
                                    }

                                # Format price if available
                                price_display = "N/A"
                                if (
                                    is_available
                                    and price_info
                                    and price_info.get("purchase")
                                ):
                                    try:
                                        price_value = price_info.get("purchase", 0)
                                        price_display = f"${price_value/1000000:.2f}"
                                    except (TypeError, ValueError) as e:
                                        logger.error(
                                            f"Error formatting price for {domain}: {str(e)}"
                                        )
                                        price_display = "Error"

                                # Create result object
                                result = {
                                    "name": name,
                                    "ext": ext,
                                    "domain": domain,
                                    "available": is_available,
                                    "price": price_display,
                                    "score": domain_score,
                                    "error": error,
                                    "providers": providers,  # Add providers to the result
                                }

                                chunk_results.append(result)

                            results.extend(chunk_results)

                            # Add a small delay between chunks to avoid rate limiting
                            if i + chunk_size < len(domain_checks):
                                await asyncio.sleep(
                                    0.05
                                )  # Reduced from 0.1 for faster processing

                        except Exception as chunk_error:
                            logger.error(
                                f"Error processing chunk {i}: {str(chunk_error)}"
                            )
                            # Continue with the next chunk instead of failing completely
                            continue

                    # Organize results by brand name
                    name_results = {}
                    for result in results:
                        try:
                            name = result["name"]
                            if name not in name_results:
                                name_results[name] = {"name": name, "domains": {}}

                            # Log the providers information before adding to the result
                            if result["available"]:
                                logger.info(
                                    f"Adding providers for {result['domain']}: {result.get('providers', {})}"
                                )

                            name_results[name]["domains"][result["ext"]] = {
                                "domain": result["domain"],
                                "available": result["available"],
                                "price": result["price"],
                                "score": result["score"],
                                "error": result["error"],
                                "providers": result.get(
                                    "providers", {}
                                ),  # Add providers to the domain info
                            }

                            # Log the final domain info with providers
                            if result["available"]:
                                logger.info(
                                    f"Final domain info for {result['domain']}: {name_results[name]['domains'][result['ext']]}"
                                )

                        except Exception as result_error:
                            logger.error(
                                f"Error processing result: {str(result_error)}"
                            )

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

        except BrandGeneratorError:
            raise
        except Exception as e:
            raise NameGenerationError(keywords, str(e))
