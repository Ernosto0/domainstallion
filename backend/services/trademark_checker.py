import aiohttp
import logging
from typing import Dict, Optional
import os
from datetime import datetime

logger = logging.getLogger(__name__)

# USPTO API endpoint
USPTO_API_URL = "https://developer.uspto.gov/ibd-api/v1/trademark/search"


class TrademarkCheckError(Exception):
    def __init__(
        self,
        message: str,
        trademark: str,
        error_code: str,
        details: Optional[Dict] = None,
    ):
        self.message = message
        self.trademark = trademark
        self.error_code = error_code
        self.details = details or {}
        super().__init__(message)


async def check_trademark(domain_name: str) -> Dict:
    """
    Check if a domain name has any trademark conflicts using USPTO API
    Returns trademark status and details if found
    """
    try:
        # Remove TLD and special characters for trademark search
        search_term = domain_name.split(".")[0].lower()
        search_term = "".join(e for e in search_term if e.isalnum())

        if not search_term:
            raise TrademarkCheckError(
                message="Invalid domain name for trademark search",
                trademark=domain_name,
                error_code="INVALID_DOMAIN",
            )

        # Construct the search query
        params = {
            "searchText": search_term,
            "searchType": "EXACT",
            "registrationStatus": "LIVE",
            "start": 0,
            "limit": 10,
        }

        async with aiohttp.ClientSession() as session:
            try:
                async with session.get(
                    USPTO_API_URL, params=params, timeout=30
                ) as response:
                    if response.status == 200:
                        data = await response.json()

                        results = data.get("results", [])
                        total_results = data.get("totalResults", 0)

                        return {
                            "has_trademark": total_results > 0,
                            "total_matches": total_results,
                            "matches": (
                                [
                                    {
                                        "serial_number": result.get("serialNumber"),
                                        "registration_number": result.get(
                                            "registrationNumber"
                                        ),
                                        "mark_text": result.get("markText"),
                                        "filing_date": result.get("filingDate"),
                                        "registration_date": result.get(
                                            "registrationDate"
                                        ),
                                        "status": result.get("status"),
                                        "owner": result.get("owner", {}).get("name"),
                                    }
                                    for result in results[:5]  # Limit to top 5 matches
                                ]
                                if total_results > 0
                                else []
                            ),
                            "error": None,
                        }

                    elif response.status == 429:
                        raise TrademarkCheckError(
                            message="Rate limit exceeded for USPTO API",
                            trademark=search_term,
                            error_code="RATE_LIMIT_EXCEEDED",
                            details={
                                "retry_after": response.headers.get("Retry-After")
                            },
                        )
                    else:
                        error_text = await response.text()
                        raise TrademarkCheckError(
                            message=f"USPTO API error: {response.status}",
                            trademark=search_term,
                            error_code="API_ERROR",
                            details={
                                "status_code": response.status,
                                "response": error_text,
                            },
                        )

            except aiohttp.ClientError as e:
                raise TrademarkCheckError(
                    message="Network error while checking trademark",
                    trademark=search_term,
                    error_code="NETWORK_ERROR",
                    details={"error": str(e)},
                )

    except TrademarkCheckError:
        raise
    except Exception as e:
        raise TrademarkCheckError(
            message="Unexpected error while checking trademark",
            trademark=domain_name,
            error_code="UNEXPECTED_ERROR",
            details={"error": str(e)},
        )
