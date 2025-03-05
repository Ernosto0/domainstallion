import re
import nltk  # type: ignore
from nltk.corpus import words  # type: ignore
import os
import logging
from typing import Dict, Any

logger = logging.getLogger(__name__)

# Download required NLTK data
try:
    nltk.data.find("corpora/words")
except LookupError:
    nltk.download("words")

english_words = set(words.words())


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

            words_in_name = name.lower().split("-")
            real_words = [word for word in words_in_name if word in english_words]

            if len(real_words) > 0:
                percentage = len(real_words) / len(words_in_name)
                if percentage == 1:
                    return {"score": 100, "description": "All real words"}
                elif percentage >= 0.5:
                    return {"score": 80, "description": "Contains real words"}
                else:
                    return {"score": 60, "description": "Has some real words"}
            return {"score": 40, "description": "No real words"}
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

            # Log individual scores
            logger.debug(f"Scoring domain: {domain_name}.{tld}")
            logger.debug(f"Length score: {length_score}")
            logger.debug(f"Dictionary score: {dictionary_score}")
            logger.debug(f"Pronounceability score: {pronounce_score}")
            logger.debug(f"Repetition score: {repetition_score}")
            logger.debug(f"TLD score: {tld_score}")

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

            logger.debug(f"Total score: {total_score}")

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
