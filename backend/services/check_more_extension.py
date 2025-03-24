import logging
import asyncio
from typing import Dict, List
from .domain_checker import check_multiple_domains
from .domain_scorer import DomainScorer

logger = logging.getLogger(__name__)

# List of all available extensions we support
ALL_EXTENSIONS = [
    "com", "net", "org", "io", "ai", "app", 
    "dev", "tech",
]

async def check_more_extensions(domain_name: str, already_checked_extensions: List[str]) -> Dict:
    """
    Check domain availability for additional extensions that weren't initially selected.
    
    Args:
        domain_name: Base domain name without extension (e.g. "example")
        already_checked_extensions: List of extensions already checked (e.g. ["com", "ai"])
        
    Returns:
        Dictionary mapping full domain names to availability information
    """
    logger.info(f"Checking more extensions for domain: {domain_name}")
    logger.info(f"Already checked extensions: {already_checked_extensions}")
    
    # Filter out extensions already checked
    extensions_to_check = [ext for ext in ALL_EXTENSIONS if ext not in already_checked_extensions]
    
    if not extensions_to_check:
        logger.info("No additional extensions to check")
        return {}
    
    logger.info(f"Extensions to check: {extensions_to_check}")
    
    # Create full domain names for each extension
    domains_to_check = [f"{domain_name}.{ext}" for ext in extensions_to_check]
    
    # Call domain_checker to check availability
    try:
        results = await check_multiple_domains(domains_to_check)
        logger.info(f"Successfully checked {len(results)} additional extensions")
        
        # Add domain scores
        domain_scorer = DomainScorer()
        for full_domain, info in results.items():
            try:
                # Extract the TLD (extension)
                extension = full_domain.split('.')[-1]
                
                # Calculate the score
                score = domain_scorer.calculate_total_score(domain_name, extension)
                
                # Add score to the result
                info['score'] = score
                logger.info(f"Added score for {full_domain}: {score['total_score']}")
            except Exception as e:
                logger.error(f"Error calculating score for {full_domain}: {str(e)}")
                # Create a default score if scoring fails
                info['score'] = {
                    "total_score": 50,
                    "details": {
                        "length": {"score": 50, "description": "Score calculation error"},
                        "dictionary": {"score": 50, "description": "Score calculation error"},
                        "pronounceability": {"score": 50, "description": "Score calculation error"},
                        "repetition": {"score": 50, "description": "Score calculation error"},
                        "tld": {"score": 50, "description": "Score calculation error"}
                    }
                }
        
        return results
    except Exception as e:
        logger.error(f"Error checking more extensions for {domain_name}: {str(e)}")
        return {} 