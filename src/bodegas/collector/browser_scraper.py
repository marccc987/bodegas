"""Script para procesar datos extraídos de perfiles de X via navegador."""

import json
import re
import logging
from datetime import datetime

logger = logging.getLogger(__name__)


def parse_count(value: str) -> int:
    """Parsear conteos como '1.2K', '3.5M', '1,234', etc."""
    if not value:
        return 0
    value = value.strip().replace(",", "").replace(".", "")

    # Handle K/M suffixes
    upper = value.upper()
    if upper.endswith("K"):
        try:
            return int(float(value[:-1].replace(",", "")) * 1000)
        except ValueError:
            pass
    if upper.endswith("M"):
        try:
            return int(float(value[:-1].replace(",", "")) * 1_000_000)
        except ValueError:
            pass

    # Try direct parse
    try:
        return int(re.sub(r"[^\d]", "", value))
    except (ValueError, TypeError):
        return 0


def parse_join_date(text: str) -> datetime | None:
    """Parsear fecha de unión como 'Se unió el mayo de 2023'."""
    months = {
        "enero": 1, "febrero": 2, "marzo": 3, "abril": 4,
        "mayo": 5, "junio": 6, "julio": 7, "agosto": 8,
        "septiembre": 9, "octubre": 10, "noviembre": 11, "diciembre": 12,
        "january": 1, "february": 2, "march": 3, "april": 4,
        "may": 5, "june": 6, "july": 7, "august": 8,
        "september": 9, "october": 10, "november": 11, "december": 12,
    }
    text_lower = text.lower()
    year_match = re.search(r"(\d{4})", text_lower)
    if not year_match:
        return None
    year = int(year_match.group(1))

    month = 1
    for name, num in months.items():
        if name in text_lower:
            month = num
            break

    return datetime(year, month, 1)


def parse_engagement_number(text: str) -> int:
    """Extraer número de texto como '385 Respuestas. Respuesta'."""
    match = re.match(r"([\d,.]+)", text.strip())
    if match:
        return parse_count(match.group(1))
    return 0


def process_profile_data(raw_profile: dict, raw_tweets: dict) -> dict:
    """Procesar datos crudos del navegador en formato limpio."""
    profile = {
        "username": raw_profile.get("username", ""),
        "display_name": raw_profile.get("displayName", ""),
        "bio": raw_profile.get("bio", "").strip(),
        "location": raw_profile.get("location", ""),
        "followers_count": parse_count(str(raw_profile.get("followers", "0"))),
        "following_count": parse_count(str(raw_profile.get("following", "0"))),
        "tweet_count": parse_count(str(raw_tweets.get("postsCount", "0"))),
        "created_at": parse_join_date(raw_profile.get("joinDate", "")),
        "has_avatar": raw_profile.get("hasAvatar", False),
        "has_bio": bool(raw_profile.get("bio", "").strip()),
        "is_verified": raw_profile.get("verified", False),
        "avatar_url": raw_profile.get("avatarUrl", ""),
    }

    tweets = []
    for t in raw_tweets.get("recentTweets", []):
        tweets.append({
            "text": t.get("text", ""),
            "created_at": t.get("time", ""),
            "is_retweet": t.get("isRT", False),
            "mentions": t.get("mentions", []),
            "replies": parse_engagement_number(str(t.get("replies", "0"))),
            "retweets": parse_engagement_number(str(t.get("retweets", "0"))),
            "likes": parse_engagement_number(str(t.get("likes", "0"))),
        })

    return {"profile": profile, "tweets": tweets}
