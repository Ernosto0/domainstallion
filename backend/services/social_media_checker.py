import aiohttp
import asyncio
import requests
import logging
from typing import Dict, Optional, List

logger = logging.getLogger(__name__)

# Social media platforms with profile URLs and unique text to detect username availability
SOCIAL_MEDIA_PLATFORMS = {
    "Twitter": {
        "url": "https://lightbrd.com/{}",
        "status_code": 404,
    },  # 404 means available
    "YouTube": {"url": "https://www.youtube.com/{}", "status_code": 404},
    "Reddit": {
        "url": "https://www.reddit.com/user/{}",
        "not_found": "Sorry, nobody on Reddit goes by that name",
    },
}


class SocialMediaCheckError(Exception):
    def __init__(
        self,
        message: str,
        username: str,
        error_code: str,
        details: Optional[Dict] = None,
    ):
        self.message = message
        self.username = username
        self.error_code = error_code
        self.details = details or {}
        super().__init__(message)


async def check_single_platform(session, platform, data, username):
    """Asynchronously checks username availability on a single platform."""
    url = data["url"].format(username)
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/114.0.0.0 Safari/537.36",
        "Accept-Language": "en-US,en;q=0.9",
        "Referer": "https://nitter.net/",
    }

    try:
        async with session.get(url, headers=headers, timeout=5, ssl=False) as response:
            page_content = await response.text()

            if "status_code" in data and response.status == data["status_code"]:
                return platform, {"available": True, "status": "Available"}
            elif (
                "not_found" in data
                and data["not_found"].lower() in page_content.lower()
            ):
                return platform, {"available": True, "status": "Available"}
            elif response.status == 200:
                return platform, {"available": False, "status": "Taken"}
            else:
                return platform, {
                    "available": None,
                    "status": f"Unknown ({response.status})",
                }

    except Exception as e:
        logger.error(f"Error checking {platform} for username {username}: {str(e)}")
        return platform, {"available": None, "status": "Error", "error": str(e)}


async def check_social_media(username: str) -> Dict:
    """
    Checks username availability across multiple social media platforms
    Returns availability status for each platform
    """
    try:
        if not username or not username.strip():
            raise SocialMediaCheckError(
                message="Invalid username for social media check",
                username=username,
                error_code="INVALID_USERNAME",
            )

        # Clean the username - remove special characters
        clean_username = "".join(e for e in username if e.isalnum() or e == "_")

        if not clean_username:
            raise SocialMediaCheckError(
                message="Username contains no valid characters",
                username=username,
                error_code="INVALID_USERNAME",
            )

        results = {}

        # Force HTTP/1.1 instead of HTTP/2 to avoid bot detection
        connector = aiohttp.TCPConnector(force_close=True)

        async with aiohttp.ClientSession(connector=connector) as session:
            tasks = [
                check_single_platform(session, platform, data, clean_username)
                for platform, data in SOCIAL_MEDIA_PLATFORMS.items()
                if platform != "Twitter"  # Handle Twitter separately
            ]
            results_list = await asyncio.gather(*tasks)
            results.update(dict(results_list))

        # Use `requests` for Twitter/X instead of `aiohttp` (to avoid 403 errors)
        twitter_url = SOCIAL_MEDIA_PLATFORMS["Twitter"]["url"].format(clean_username)
        try:
            response = requests.get(
                twitter_url,
                headers={
                    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/114.0.0.0 Safari/537.36"
                },
                timeout=5,
            )
            if response.status_code == 404:
                results["Twitter"] = {"available": True, "status": "Available"}
            elif response.status_code == 200:
                results["Twitter"] = {"available": False, "status": "Taken"}
            else:
                results["Twitter"] = {
                    "available": None,
                    "status": f"Unknown ({response.status_code})",
                }
        except requests.RequestException as e:
            logger.error(
                f"Error checking Twitter for username {clean_username}: {str(e)}"
            )
            results["Twitter"] = {"available": None, "status": "Error", "error": str(e)}

        # Format the response
        return {
            "username": clean_username,
            "platforms": results,
            "available_count": sum(
                1 for platform in results.values() if platform.get("available") is True
            ),
            "taken_count": sum(
                1 for platform in results.values() if platform.get("available") is False
            ),
            "error_count": sum(
                1 for platform in results.values() if platform.get("available") is None
            ),
        }

    except SocialMediaCheckError:
        raise
    except Exception as e:
        raise SocialMediaCheckError(
            message="Unexpected error while checking social media availability",
            username=username,
            error_code="UNEXPECTED_ERROR",
            details={"error": str(e)},
        )
