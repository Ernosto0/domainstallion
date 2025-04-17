import re
import os
import logging
import json
from typing import Dict, Any, Set
from pathlib import Path

logger = logging.getLogger(__name__)

# Create a simple English word list 
class WordList:
    def __init__(self):
        self.words = set()
        self._load_words()
    
    def _load_words(self):
        # Define a minimal set of common words as fallback
        minimal_words = {"domain", "app", "tech", "web", "site", "shop", "data", "cloud", "mobile", "code"}
        
        # Define common words
        common_words = {
            "the", "be", "to", "of", "and", "a", "in", "that", "have", "i", 
            "it", "for", "not", "on", "with", "he", "as", "you", "do", "at", 
            "this", "but", "his", "by", "from", "they", "we", "say", "her", "she", 
            "or", "an", "will", "my", "one", "all", "would", "there", "their", "what", 
            "so", "up", "out", "if", "about", "who", "get", "which", "go", "me",
            "when", "make", "can", "like", "time", "no", "just", "him", "know", "take", 
            "people", "into", "year", "your", "good", "some", "could", "them", "see", "other", 
            "than", "then", "now", "look", "only", "come", "its", "over", "think", "also", 
            "back", "after", "use", "two", "how", "our", "work", "first", "well", "way", 
            "even", "new", "want", "because", "any", "these", "give", "day", "most", "us",
            "app", "web", "site", "tech", "cloud", "data", "shop", "store", "online", "digital",
            "blog", "health", "food", "smart", "easy", "fast", "simple", "quick", "best", "top",
            "design", "market", "social", "media", "mobile", "code", "game", "play", "learn", "help"
        }
        
        # Add domain-relevant words
        domain_words = {
            "domain", "brand", "business", "company", "enterprise", "service", "product", "solution",
            "platform", "network", "system", "software", "hardware", "info", "group", "team",
            "agency", "studio", "labs", "hub", "space", "zone", "world", "global", "local",
            "pro", "expert", "guru", "master", "ninja", "wizard", "genius", "connect", "link",
            # Tech terms
            "tech", "technology", "digital", "cyber", "net", "web", "app", "robot", "bot", "ai",
            "cloud", "data", "analytics", "crypto", "secure", "safe", "privacy", "private", "public",
            "mobile", "virtual", "reality", "augmented", "wireless", "iot", "internet", "things", 
            "automation", "auto", "smart", "intelligence", "machine", "learning", "deep", "neural",
            "blockchain", "token", "nft", "meta", "metaverse", "quantum", "nano", "micro", "macro",
            "code", "coding", "program", "programming", "dev", "develop", "developer", "stack", 
            "frontend", "backend", "fullstack", "ui", "ux", "design", "designer", "creative",
            # Business terms
            "market", "finance", "fintech", "invest", "investor", "money", "bank", "banking", "pay",
            "shop", "store", "commerce", "buy", "sell", "trade", "trading", "exchange", "auction",
            "retail", "wholesale", "consumer", "customer", "client", "user", "account", "premium",
            "plan", "subscription", "monthly", "annual", "yearly", "daily", "weekly", "free", "pro",
            "startup", "scale", "growth", "venture", "capital", "fund", "funding", "angel", "seed",
            "series", "ipo", "exit", "merger", "acquisition", "partner", "alliance", "collaborate",
            # Industry terms
            "health", "medical", "medicine", "pharma", "doctor", "patient", "care", "wellness",
            "fitness", "exercise", "workout", "gym", "yoga", "mindful", "mental", "physical",
            "food", "eat", "nutrition", "diet", "recipe", "cook", "cooking", "kitchen", "meal",
            "travel", "trip", "vacation", "hotel", "flight", "booking", "reservation", "tour",
            "education", "learn", "course", "class", "school", "college", "university", "academy",
            "legal", "law", "lawyer", "attorney", "counsel", "advice", "consult", "consultant",
            "real", "estate", "property", "home", "house", "apartment", "rent", "buy", "sell",
            # Social terms
            "social", "media", "network", "community", "group", "forum", "chat", "message", "email",
            "friend", "follow", "follower", "share", "like", "comment", "post", "video", "photo",
            "image", "picture", "stream", "live", "streaming", "broadcast", "channel", "content",
            # Common brand elements
            "go", "get", "try", "use", "make", "build", "create", "find", "discover", "explore",
            "fast", "quick", "rapid", "swift", "instant", "now", "today", "tomorrow", "future",
            "easy", "simple", "lite", "light", "basic", "advanced", "pro", "plus", "premium",
            "fresh", "new", "novel", "innovative", "disruptive", "revolutionary", "evolve",
            "bright", "clear", "vivid", "bold", "strong", "power", "powerful", "super", "ultra",
            "cool", "awesome", "amazing", "incredible", "fantastic", "great", "good", "best",
            "first", "primary", "main", "central", "core", "essential", "vital", "key", "prime",
            "alpha", "beta", "delta", "sigma", "omega", "zen", "eco", "green", "blue", "red"
        }
        
        # Path to the word list file
        word_file_path = Path(__file__).parent / "english_words.json"
        
        # Try to load from file first
        try:
            if word_file_path.exists():
                with open(word_file_path, 'r') as f:
                    self.words = set(json.load(f))
                logger.info(f"Loaded {len(self.words)} words from local file")
                return
        except Exception as e:
            logger.error(f"Error loading word list from file: {str(e)}")
        
        # If we get here, either the file doesn't exist or there was an error
        # Use the common words and domain words
        self.words = common_words.union(domain_words)
        logger.info(f"Using basic word set with {len(self.words)} words")
        
        # Try to save the word list for future use
        try:
            with open(word_file_path, 'w') as f:
                json.dump(list(self.words), f)
            logger.info(f"Saved basic word list to {word_file_path}")
        except Exception as e:
            logger.warning(f"Could not save word list: {str(e)}")
            # If all else fails, use minimal word set
            if not self.words:
                self.words = minimal_words
                logger.warning("Falling back to minimal word set")
    
    def contains(self, word: str) -> bool:
        """Check if the word exists in our word list."""
        return word.lower() in self.words
    
    def find_words_in_text(self, text: str) -> list:
        """Find all words in a given text that exist in our word list."""
        text = text.lower()
        found_words = []
        
        # First check if the entire text is a word
        if self.contains(text):
            found_words.append(text)
            return found_words
        
        # Check for hyphenated words
        if "-" in text:
            parts = text.split("-")
            for part in parts:
                if self.contains(part):
                    found_words.append(part)
            if found_words:
                return found_words
        
        # Try to find subwords with a minimum length of 3
        min_word_length = 3
        for word in self.words:
            if len(word) >= min_word_length and word in text:
                found_words.append(word)
        
        return found_words

# Initialize the word list
english_words = WordList()


class DomainScorerError(Exception):
    def __init__(self, message: str, error_code: str, details: Dict[str, Any] = None):
        self.message = message
        self.error_code = error_code
        self.details = details or {}
        super().__init__(message)


class DomainScorer:
    def __init__(self):
        self.tld_scores = {
            "com": {
                "score": 100,
                "description": "Most valuable TLD",
            },
            "net": {
                "score": 60,
                "description": "Good alternative",
            },
            "org": {
                "score": 60,
                "description": "Good for organizations",
            },
            "io": {
                "score": 80,
                "description": "Popular in tech",
            },
            "ai": {
                "score": 80,
                "description": "Trending TLD",
            },
            "app": {
                "score": 80,
                "description": "Perfect for apps",
            },
            "dev": {
                "score": 60,
                "description": "Great for developers",
            },
            "xyz": {
                "score": 40,
                "description": "Less reputable",
            },
            "info": {
                "score": 40,
                "description": "Less reputable",
            },
            "biz": {
                "score": 40,
                "description": "Less reputable",
            },
        }

    def get_length_score(self, name: str) -> Dict[str, Any]:
        try:
            if not name:
                raise DomainScorerError(
                    message="Domain name cannot be empty",
                    error_code="EMPTY_DOMAIN_NAME",
                )

            length = len(name)
            if length <= 5:
                return {"score": 100, "description": "Perfect length"}
            elif length <= 10:
                return {"score": 80, "description": "Good length"}
            elif length <= 15:
                return {"score": 60, "description": "Acceptable length"}
            else:
                return {"score": 40, "description": "Too long"}
        except DomainScorerError:
            raise
        except Exception as e:
            raise DomainScorerError(
                message="Error calculating length score",
                error_code="LENGTH_SCORE_ERROR",
                details={"error": str(e)},
            )

    def get_dictionary_word_score(self, name: str) -> Dict[str, Any]:
        try:
            if not name:
                raise DomainScorerError(
                    message="Domain name cannot be empty",
                    error_code="EMPTY_DOMAIN_NAME",
                )

            # First, try the basic hyphen-separated approach (for backward compatibility)
            words_in_name = name.lower().split("-")
            real_words = [word for word in words_in_name if english_words.contains(word)]
            
            # If no words found, use the more advanced method
            if not real_words:
                real_words = english_words.find_words_in_text(name.lower())
            
            if len(real_words) > 0:
                # Calculate how much of the domain name is covered by real words
                total_chars = len(name)
                covered_chars = sum(len(word) for word in real_words)
                coverage_ratio = min(1.0, covered_chars / total_chars)  # Cap at 100%
                
                if coverage_ratio >= 0.9:
                    return {"score": 100, "description": "Contains meaningful words"}
                elif coverage_ratio >= 0.6:
                    return {"score": 80, "description": "Contains recognizable words"}
                elif coverage_ratio >= 0.3:
                    return {"score": 60, "description": "Contains some word elements"}
                else:
                    return {"score": 40, "description": "Few word elements"}
            return {"score": 40, "description": "No recognizable words"}
        except DomainScorerError:
            raise
        except Exception as e:
            raise DomainScorerError(
                message="Error calculating dictionary score",
                error_code="DICTIONARY_SCORE_ERROR",
                details={"error": str(e)},
            )

    def get_pronounceability_score(self, name: str) -> Dict[str, Any]:
        try:
            if not name:
                raise DomainScorerError(
                    message="Domain name cannot be empty",
                    error_code="EMPTY_DOMAIN_NAME",
                )

            vowels = "aeiou"
            name = name.lower()
            vowel_count = sum(1 for letter in name if letter in vowels)
            consonant_count = len(name) - vowel_count

            if consonant_count == 0:
                return {"score": 100, "description": "Very easy to pronounce"}

            ratio = vowel_count / consonant_count

            if ratio >= 0.4:
                return {"score": 100, "description": "Very easy to pronounce"}
            elif ratio >= 0.3:
                return {"score": 80, "description": "Easy to pronounce"}
            elif ratio >= 0.2:
                return {"score": 60, "description": "Moderately pronounceable"}
            else:
                return {"score": 40, "description": "Hard to pronounce"}
        except DomainScorerError:
            raise
        except Exception as e:
            raise DomainScorerError(
                message="Error calculating pronounceability score",
                error_code="PRONOUNCEABILITY_SCORE_ERROR",
                details={"error": str(e)},
            )

    def get_repeated_letter_score(self, name: str) -> Dict[str, Any]:
        try:
            if not name:
                raise DomainScorerError(
                    message="Domain name cannot be empty",
                    error_code="EMPTY_DOMAIN_NAME",
                )

            has_doubles = bool(re.search(r"(.)\1", name))
            if has_doubles:
                return {"score": 100, "description": "Has catchy letter repetition"}
            return {"score": 60, "description": "No letter repetition"}
        except DomainScorerError:
            raise
        except Exception as e:
            raise DomainScorerError(
                message="Error calculating repetition score",
                error_code="REPETITION_SCORE_ERROR",
                details={"error": str(e)},
            )

    def get_tld_score(self, tld: str) -> Dict[str, Any]:
        try:
            if not tld:
                raise DomainScorerError(
                    message="TLD cannot be empty", error_code="EMPTY_TLD"
                )

            tld = tld.lower().lstrip(".")
            return self.tld_scores.get(
                tld, {"score": 20, "description": "Uncommon TLD"}
            )
        except DomainScorerError:
            raise
        except Exception as e:
            raise DomainScorerError(
                message="Error calculating TLD score",
                error_code="TLD_SCORE_ERROR",
                details={"error": str(e)},
            )

    def calculate_total_score(self, domain_name: str, tld: str) -> Dict[str, Any]:
        try:
            if not domain_name or not tld:
                raise DomainScorerError(
                    message="Domain name and TLD are required",
                    error_code="MISSING_PARAMETERS",
                    details={"domain_name": bool(domain_name), "tld": bool(tld)},
                )

            # Split domain into name and extension
            name = domain_name.lower()

            # Calculate individual scores
            length_score = self.get_length_score(name)
            dictionary_score = self.get_dictionary_word_score(name)
            pronounce_score = self.get_pronounceability_score(name)
            repetition_score = self.get_repeated_letter_score(name)
            tld_score = self.get_tld_score(tld)


            # Calculate weighted average
            total_score = (
                length_score["score"] * 0.2
                + dictionary_score["score"] * 0.2
                + pronounce_score["score"] * 0.2
                + repetition_score["score"] * 0.2
                + tld_score["score"] * 0.2
            )

            # Round to nearest whole number
            total_score = round(total_score)



            return {
                "total_score": total_score,
                "details": {
                    "length": length_score,
                    "dictionary": dictionary_score,
                    "pronounceability": pronounce_score,
                    "repetition": repetition_score,
                    "tld": tld_score,
                },
            }
        except DomainScorerError:
            raise
        except Exception as e:
            raise DomainScorerError(
                message="Error calculating total score",
                error_code="TOTAL_SCORE_ERROR",
                details={"domain_name": domain_name, "tld": tld, "error": str(e)},
            )
