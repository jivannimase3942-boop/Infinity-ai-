"""
Infinity AI - Real-time Date, Time & Timezone Engine
Operates 100% locally and offline using the system clock and Python's
timezone-aware datetime APIs (zoneinfo / tzdata / dateutil).

Provides deterministic, accurate date and time answers without hallucination.
Default timezone for India is Asia/Kolkata.
Supports explicit global timezones, major cities, abbreviations, and DST rules.
"""

from datetime import datetime, timezone
import re
from typing import Dict, Any, Optional, Tuple

try:
    import zoneinfo
except ImportError:
    zoneinfo = None

try:
    import dateutil.tz as dateutil_tz
except ImportError:
    dateutil_tz = None

DEFAULT_TIMEZONE = "Asia/Kolkata"

# Mapping of common city names, country names, regions, and abbreviations to IANA timezone identifiers
CITY_TIMEZONE_MAP: Dict[str, str] = {
    # India (Default)
    "india": "Asia/Kolkata",
    "kolkata": "Asia/Kolkata",
    "calcutta": "Asia/Kolkata",
    "mumbai": "Asia/Kolkata",
    "delhi": "Asia/Kolkata",
    "new delhi": "Asia/Kolkata",
    "bengaluru": "Asia/Kolkata",
    "bangalore": "Asia/Kolkata",
    "chennai": "Asia/Kolkata",
    "hyderabad": "Asia/Kolkata",
    "pune": "Asia/Kolkata",
    "ahmedabad": "Asia/Kolkata",
    "jaipur": "Asia/Kolkata",
    "ist": "Asia/Kolkata",

    # United Kingdom & Western Europe
    "london": "Europe/London",
    "uk": "Europe/London",
    "united kingdom": "Europe/London",
    "england": "Europe/London",
    "britain": "Europe/London",
    "scotland": "Europe/London",
    "edinburgh": "Europe/London",
    "belfast": "Europe/London",
    "dublin": "Europe/Dublin",
    "ireland": "Europe/Dublin",
    "lisbon": "Europe/Lisbon",
    "portugal": "Europe/Lisbon",

    # Central & Eastern Europe
    "paris": "Europe/Paris",
    "france": "Europe/Paris",
    "berlin": "Europe/Berlin",
    "germany": "Europe/Berlin",
    "frankfurt": "Europe/Berlin",
    "munich": "Europe/Berlin",
    "rome": "Europe/Rome",
    "italy": "Europe/Rome",
    "madrid": "Europe/Madrid",
    "spain": "Europe/Madrid",
    "barcelona": "Europe/Madrid",
    "amsterdam": "Europe/Amsterdam",
    "netherlands": "Europe/Amsterdam",
    "brussels": "Europe/Brussels",
    "belgium": "Europe/Brussels",
    "zurich": "Europe/Zurich",
    "switzerland": "Europe/Zurich",
    "geneva": "Europe/Zurich",
    "vienna": "Europe/Vienna",
    "austria": "Europe/Vienna",
    "stockholm": "Europe/Stockholm",
    "sweden": "Europe/Stockholm",
    "oslo": "Europe/Oslo",
    "norway": "Europe/Oslo",
    "copenhagen": "Europe/Copenhagen",
    "denmark": "Europe/Copenhagen",
    "helsinki": "Europe/Helsinki",
    "finland": "Europe/Helsinki",
    "warsaw": "Europe/Warsaw",
    "poland": "Europe/Warsaw",
    "prague": "Europe/Prague",
    "czech republic": "Europe/Prague",
    "athens": "Europe/Athens",
    "greece": "Europe/Athens",
    "moscow": "Europe/Moscow",
    "russia": "Europe/Moscow",
    "kyiv": "Europe/Kyiv",
    "kiev": "Europe/Kyiv",
    "ukraine": "Europe/Kyiv",
    "cet": "Europe/Paris",
    "cest": "Europe/Paris",
    "eet": "Europe/Athens",

    # North America
    "new york": "America/New_York",
    "nyc": "America/New_York",
    "washington": "America/New_York",
    "dc": "America/New_York",
    "boston": "America/New_York",
    "miami": "America/New_York",
    "atlanta": "America/New_York",
    "philadelphia": "America/New_York",
    "toronto": "America/Toronto",
    "montreal": "America/Toronto",
    "ottawa": "America/Toronto",
    "est": "America/New_York",
    "edt": "America/New_York",

    "chicago": "America/Chicago",
    "houston": "America/Chicago",
    "dallas": "America/Chicago",
    "austin": "America/Chicago",
    "cst": "America/Chicago",
    "cdt": "America/Chicago",

    "denver": "America/Denver",
    "phoenix": "America/Phoenix",
    "arizona": "America/Phoenix",
    "mst": "America/Denver",
    "mdt": "America/Denver",

    "los angeles": "America/Los_Angeles",
    "la": "America/Los_Angeles",
    "san francisco": "America/Los_Angeles",
    "sf": "America/Los_Angeles",
    "california": "America/Los_Angeles",
    "seattle": "America/Los_Angeles",
    "vancouver": "America/Vancouver",
    "pst": "America/Los_Angeles",
    "pdt": "America/Los_Angeles",

    "honolulu": "Pacific/Honolulu",
    "hawaii": "Pacific/Honolulu",
    "anchorage": "America/Anchorage",
    "alaska": "America/Anchorage",

    # Latin America
    "mexico city": "America/Mexico_City",
    "mexico": "America/Mexico_City",
    "sao paulo": "America/Sao_Paulo",
    "brazil": "America/Sao_Paulo",
    "buenos aires": "America/Argentina/Buenos_Aires",
    "argentina": "America/Argentina/Buenos_Aires",
    "santiago": "America/Santiago",
    "chile": "America/Santiago",
    "bogota": "America/Bogota",
    "colombia": "America/Bogota",
    "lima": "America/Lima",
    "peru": "America/Lima",

    # Middle East
    "dubai": "Asia/Dubai",
    "uae": "Asia/Dubai",
    "abu dhabi": "Asia/Dubai",
    "doha": "Asia/Qatar",
    "qatar": "Asia/Qatar",
    "riyadh": "Asia/Riyadh",
    "saudi arabia": "Asia/Riyadh",
    "kuwait": "Asia/Kuwait",
    "tel aviv": "Asia/Jerusalem",
    "jerusalem": "Asia/Jerusalem",
    "israel": "Asia/Jerusalem",
    "istanbul": "Europe/Istanbul",
    "turkey": "Europe/Istanbul",

    # Asia & Pacific
    "tokyo": "Asia/Tokyo",
    "japan": "Asia/Tokyo",
    "jst": "Asia/Tokyo",
    "seoul": "Asia/Seoul",
    "korea": "Asia/Seoul",
    "south korea": "Asia/Seoul",
    "kst": "Asia/Seoul",
    "beijing": "Asia/Shanghai",
    "shanghai": "Asia/Shanghai",
    "china": "Asia/Shanghai",
    "cst_china": "Asia/Shanghai",
    "hong kong": "Asia/Hong_Kong",
    "hk": "Asia/Hong_Kong",
    "taipei": "Asia/Taipei",
    "taiwan": "Asia/Taipei",
    "singapore": "Asia/Singapore",
    "sgt": "Asia/Singapore",
    "kuala lumpur": "Asia/Kuala_Lumpur",
    "malaysia": "Asia/Kuala_Lumpur",
    "bangkok": "Asia/Bangkok",
    "thailand": "Asia/Bangkok",
    "jakarta": "Asia/Jakarta",
    "indonesia": "Asia/Jakarta",
    "manila": "Asia/Manila",
    "philippines": "Asia/Manila",
    "hanoi": "Asia/Ho_Chi_Minh",
    "vietnam": "Asia/Ho_Chi_Minh",
    "dhaka": "Asia/Dhaka",
    "bangladesh": "Asia/Dhaka",
    "colombo": "Asia/Colombo",
    "sri lanka": "Asia/Colombo",
    "kathmandu": "Asia/Kathmandu",
    "nepal": "Asia/Kathmandu",
    "karachi": "Asia/Karachi",
    "lahore": "Asia/Karachi",
    "pakistan": "Asia/Karachi",

    # Australia & Oceania
    "sydney": "Australia/Sydney",
    "melbourne": "Australia/Melbourne",
    "canberra": "Australia/Sydney",
    "brisbane": "Australia/Brisbane",
    "adelaide": "Australia/Adelaide",
    "perth": "Australia/Perth",
    "australia": "Australia/Sydney",
    "aest": "Australia/Sydney",
    "aedt": "Australia/Sydney",
    "auckland": "Pacific/Auckland",
    "wellington": "Pacific/Auckland",
    "new zealand": "Pacific/Auckland",
    "nz": "Pacific/Auckland",

    # Africa
    "cairo": "Africa/Cairo",
    "egypt": "Africa/Cairo",
    "johannesburg": "Africa/Johannesburg",
    "south africa": "Africa/Johannesburg",
    "cape town": "Africa/Johannesburg",
    "nairobi": "Africa/Nairobi",
    "kenya": "Africa/Nairobi",
    "lagos": "Africa/Lagos",
    "nigeria": "Africa/Lagos",

    # Standard / Reference
    "utc": "UTC",
    "gmt": "UTC",
    "zulu": "UTC",
}

# Regex patterns to detect date/time queries
DATE_TIME_PATTERNS = [
    # Explicit time queries
    r"^(what('s| is) (the )?time(\??|\.?)?)$",
    r"\bwhat time is it\b",
    r"\bwhat is the (current )?time\b",
    r"\bwhat's the (current )?time\b",
    r"\btell me the (current )?time\b",
    r"\bcurrent time\b",
    r"\btime right now\b",

    # Explicit date queries
    r"^(what('s| is) (today'?s?|the) date(\??|\.?)?)$",
    r"\bwhat is today'?s? date\b",
    r"\bwhat's today'?s? date\b",
    r"\bwhat is the date (today)?\b",
    r"\bwhat date is (it|today)\b",
    r"\btoday'?s? date\b",
    r"\bcurrent date\b",

    # Day of week queries
    r"^(what('s| is) (the )?day (today|is it)(\??|\.?)?)$",
    r"\bwhat day is (it|today)\b",
    r"\bwhat day of the week is (it|today)\b",
    r"\bwhich day is (it|today)\b",
    r"\bwhat's today'?s? day\b",

    # Combined date & time queries
    r"\bwhat is the (current )?(date and time|time and date)\b",
    r"\bcurrent (date and time|time and date)\b",

    # Location-specific time queries
    r"\bwhat time is it in ([a-zA-Z\s_\-]+)\b",
    r"\bwhat is the time in ([a-zA-Z\s_\-]+)\b",
    r"\bwhat's the time in ([a-zA-Z\s_\-]+)\b",
    r"\b(current )?time in ([a-zA-Z\s_\-]+)\b",
    r"\btime for ([a-zA-Z\s_\-]+)\b",
    r"\bwhat is the date in ([a-zA-Z\s_\-]+)\b",
    r"\bwhat day is it in ([a-zA-Z\s_\-]+)\b",
]


def is_datetime_query(prompt: str) -> bool:
    """Detects if a user prompt is asking for the current date, time, day, or timezone."""
    if not prompt or not prompt.strip():
        return False
    clean = prompt.strip().lower()

    # Fast check against known patterns
    for pat in DATE_TIME_PATTERNS:
        if re.search(pat, clean):
            return True

    # Check for direct short questions
    short_matches = [
        "time?", "what time", "date?", "what date", "today date", "today's date",
        "which day", "what day", "current time", "current date"
    ]
    if any(m in clean for m in short_matches) and len(clean.split()) <= 8:
        return True

    return False


def get_timezone_obj(tz_name: str) -> Optional[Any]:
    """Retrieves a timezone object using zoneinfo or dateutil.tz gracefully."""
    # 1. Try zoneinfo
    if zoneinfo:
        try:
            return zoneinfo.ZoneInfo(tz_name)
        except Exception:
            pass

    # 2. Try dateutil.tz
    if dateutil_tz:
        try:
            tz = dateutil_tz.gettz(tz_name)
            if tz is not None:
                return tz
        except Exception:
            pass

    # 3. Special handling for UTC
    if tz_name.upper() in ["UTC", "GMT", "ZULU"]:
        return timezone.utc

    return None


def extract_location_from_query(prompt: str) -> Optional[str]:
    """Extracts target location or timezone specified in the prompt."""
    clean = prompt.strip().lower()

    location_patterns = [
        r"\b(?:what time is it|what is the time|what's the time|current time|time|date|day) (?:in|at|on|for) ([a-zA-Z\s_\-]+)[\?\.\!]?$",
        r"\b(?:in|at|on|for) ([a-zA-Z\s_\-]+),?\s+(?:what time is it|what's the time|what is the date|what day is it)[\?\.\!]?$",
        r"\b(?:time|date) (?:in|at|on|for) ([a-zA-Z\s_\-]+)[\?\.\!]?$",
    ]

    for pat in location_patterns:
        m = re.search(pat, clean)
        if m:
            loc = m.group(1).strip().strip("?.,! ")
            # Remove filler words
            loc = re.sub(r"^(the city of|city of|country of|the)\s+", "", loc)
            if loc and loc not in ["today", "now", "utc", "gmt", "this moment"]:
                return loc

    return None


def resolve_timezone(location_or_tz: Optional[str]) -> Tuple[Optional[str], Optional[Any], str]:
    """
    Resolves a location name or timezone identifier to (iana_name, tz_object, display_name).
    If no location is given, returns the default Asia/Kolkata timezone.
    If location is unrecognized, returns (None, None, location_or_tz).
    """
    if not location_or_tz:
        iana = DEFAULT_TIMEZONE
        tz_obj = get_timezone_obj(iana)
        return iana, tz_obj, "India (Asia/Kolkata)"

    clean_loc = location_or_tz.strip().lower()

    # Check direct dictionary lookup
    if clean_loc in CITY_TIMEZONE_MAP:
        iana = CITY_TIMEZONE_MAP[clean_loc]
        tz_obj = get_timezone_obj(iana)
        display = location_or_tz.strip().title()
        return iana, tz_obj, display

    # Check IANA timezone directly (e.g., "America/Chicago")
    direct_tz = get_timezone_obj(location_or_tz.strip())
    if direct_tz is not None:
        return location_or_tz.strip(), direct_tz, location_or_tz.strip()

    # Check word-boundary or minimum-length match in CITY_TIMEZONE_MAP
    words = set(re.findall(r"\b[a-z]{3,}\b", clean_loc))
    for k, v in CITY_TIMEZONE_MAP.items():
        if len(k) >= 4 and (k == clean_loc or k in clean_loc or (len(clean_loc) >= 4 and clean_loc in k)):
            tz_obj = get_timezone_obj(v)
            if tz_obj is not None:
                return v, tz_obj, k.title()
        elif k in words:
            tz_obj = get_timezone_obj(v)
            if tz_obj is not None:
                return v, tz_obj, k.title()

    return None, None, location_or_tz.strip()


def handle_datetime_query(prompt: str) -> Dict[str, Any]:
    """
    Processes a date/time query and generates the deterministic, live response.
    Returns:
    {
        "status": "SUCCESS" or "ERROR",
        "answer": str,
        "timezone": str,
        "iso_timestamp": str,
        "is_datetime": True
    }
    """
    clean = prompt.strip().lower()
    loc = extract_location_from_query(prompt)

    iana, tz_obj, display_name = resolve_timezone(loc)

    # If an explicit location was requested but could not be resolved
    if loc and tz_obj is None:
        # Fall back gracefully to local Indian time and explain
        default_tz = get_timezone_obj(DEFAULT_TIMEZONE)
        now_default = datetime.now(default_tz) if default_tz else datetime.now()
        local_time_str = now_default.strftime("%I:%M %p").lstrip("0")
        local_date_str = now_default.strftime("%A, %B %d, %Y")

        answer = (
            f"I couldn't identify a timezone for **'{loc}'**.\n\n"
            f"For reference, your local system time in India (**Asia/Kolkata**) is:\n"
            f"• **Time:** {local_time_str} IST\n"
            f"• **Date:** {local_date_str}\n\n"
            f"*Tip: You can ask for cities like London, New York, Tokyo, Dubai, Paris, Sydney, etc.*"
        )
        return {
            "status": "SUCCESS",
            "answer": answer,
            "timezone": DEFAULT_TIMEZONE,
            "iso_timestamp": now_default.isoformat(),
            "is_datetime": True,
            "warning": f"Unrecognized location: {loc}"
        }

    now = datetime.now(tz_obj) if tz_obj else datetime.now()

    time_str = now.strftime("%I:%M %p").lstrip("0")
    if not time_str:
        time_str = now.strftime("%H:%M")
    day_num = now.day
    date_str = f"{now.strftime('%A, %B')} {day_num}, {now.year}"
    day_str = now.strftime("%A")
    tz_abbr = now.strftime("%Z") or iana

    # Calculate UTC offset string (e.g. UTC+05:30)
    offset = now.utcoffset()
    if offset is not None:
        total_seconds = int(offset.total_seconds())
        sign = "+" if total_seconds >= 0 else "-"
        hours, remainder = divmod(abs(total_seconds), 3600)
        minutes, _ = divmod(remainder, 60)
        offset_str = f"UTC{sign}{hours:02d}:{minutes:02d}"
    else:
        offset_str = "UTC"

    # Determine query intent type
    is_time_only = any(re.search(pat, clean) for pat in [
        r"\bwhat time\b", r"\bcurrent time\b", r"\btime right now\b", r"\btell me the time\b"
    ]) and not ("date" in clean or "day" in clean)

    is_date_only = ("date" in clean or "today's date" in clean) and not ("time" in clean)
    is_day_only = ("what day" in clean or "which day" in clean) and not ("time" in clean or "date" in clean)

    if loc:
        # Location specific answer
        if is_time_only:
            answer = (
                f"The current time in **{display_name}** is **{time_str}** "
                f"({tz_abbr}, {offset_str}) on **{date_str}**."
            )
        elif is_day_only:
            answer = f"Today in **{display_name}** is **{day_str}** ({date_str})."
        elif is_date_only:
            answer = f"The date in **{display_name}** is **{date_str}**."
        else:
            answer = (
                f"In **{display_name}**:\n"
                f"• **Time:** {time_str} ({tz_abbr}, {offset_str})\n"
                f"• **Date:** {date_str}"
            )
    else:
        # Local system answer (defaults to Asia/Kolkata)
        if is_time_only:
            answer = f"The current time is **{time_str}** ({tz_abbr}, {offset_str}) on **{date_str}**."
        elif is_day_only:
            answer = f"Today is **{day_str}**."
        elif is_date_only:
            answer = f"Today's date is **{date_str}**."
        else:
            answer = (
                f"• **Current Time:** {time_str} ({tz_abbr}, {offset_str})\n"
                f"• **Today's Date:** {date_str}"
            )

    return {
        "status": "SUCCESS",
        "answer": answer,
        "timezone": iana or DEFAULT_TIMEZONE,
        "iso_timestamp": now.isoformat(),
        "is_datetime": True
    }


def get_datetime_answer(prompt: str) -> str:
    """Convenience helper returning the markdown answer string for a datetime query."""
    return handle_datetime_query(prompt).get("answer", "")

