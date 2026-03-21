"""
Job relevance scoring.
  1. Keyword scorer — fast, free, runs on every job.
  2. Claude Haiku explainer — generates "why you'd be a fit" for the top N jobs.
"""
import functools
import os
import re
from scrapers.base import Job


@functools.lru_cache(maxsize=10)
def _exp_re(threshold: int) -> re.Pattern:
    """Regex matching stated experience requirements >= threshold years."""
    # e.g. threshold=5 → leading digit class "[5-9]|[1-9]\\d" matches 5-99
    if threshold <= 9:
        leading = rf"[{threshold}-9]|[1-9]\d"
    else:
        leading = r"[1-9]\d"
    return re.compile(
        # "5+ years of experience" / "5-7 years experience" / "10 years' experience"
        # years?'? handles possessive form ("8 years' experience")
        # Allow 0-3 words between "years" and "experience" to catch varied phrasings
        rf"\b(?:{leading})\+?\s*(?:[-–]\s*\d+\s*)?\s*years?'?\s+(?:[\w\-/]+\s+){{0,3}}experience"
        # "minimum 5 years" / "at least 5 years"
        rf"|(?:minimum(?:\s+of)?|at\s+least)\s+(?:{leading})\+?\s*years?'?",
        re.IGNORECASE,
    )

try:
    import anthropic
    _CLAUDE_AVAILABLE = True
except ImportError:
    _CLAUDE_AVAILABLE = False


# ---------------------------------------------------------------------------
# US location whitelist
# ---------------------------------------------------------------------------

_US_INDICATORS = frozenset({
    # Remote / flexible
    "remote", "anywhere", "work from home", "wfh",
    # Country-level
    "united states", "usa", "u.s.", "u.s.a.",
    # DC
    "district of columbia", "washington dc", "washington d.c.",
    # All 50 state full names
    "alabama", "alaska", "arizona", "arkansas", "california", "colorado",
    "connecticut", "delaware", "florida", "georgia", "hawaii", "idaho",
    "illinois", "indiana", "iowa", "kansas", "kentucky", "louisiana",
    "maine", "maryland", "massachusetts", "michigan", "minnesota",
    "mississippi", "missouri", "montana", "nebraska", "nevada",
    "new hampshire", "new jersey", "new mexico", "new york",
    "north carolina", "north dakota", "ohio", "oklahoma", "oregon",
    "pennsylvania", "rhode island", "south carolina", "south dakota",
    "tennessee", "texas", "utah", "vermont", "virginia",
    "washington", "west virginia", "wisconsin", "wyoming",
    # Major US cities that commonly appear without a state suffix in ATS postings
    "new york city", "nyc", "los angeles", "san francisco", "chicago",
    "houston", "phoenix", "philadelphia", "san antonio", "san diego",
    "dallas", "austin", "jacksonville", "fort worth", "columbus",
    "charlotte", "indianapolis", "san jose", "seattle", "denver",
    "nashville", "oklahoma city", "el paso", "boston", "portland",
    "las vegas", "memphis", "louisville", "baltimore", "milwaukee",
    "albuquerque", "tucson", "fresno", "sacramento", "mesa",
    "atlanta", "omaha", "colorado springs", "raleigh", "miami",
    "minneapolis", "tulsa", "cleveland", "wichita", "arlington",
    "pittsburgh", "tampa", "new orleans", "honolulu", "anaheim",
    "aurora", "santa ana", "corpus christi", "riverside", "lexington",
    "st. louis", "pittsburgh", "cincinnati", "anchorage", "plano",
    "newark", "henderson", "st. paul", "greensboro", "lincoln",
    "buffalo", "fort wayne", "jersey city", "chula vista", "chandler",
    "madison", "durham", "lubbock", "winston-salem", "garland",
    "glendale", "hialeah", "reno", "baton rouge", "irvine",
    "chesapeake", "scottsdale", "north las vegas", "fremont",
    "gilbert", "san bernardino", "boise", "birmingham", "rochester",
    "richmond", "spokane", "des moines", "montgomery", "modesto",
    "fayetteville", "tacoma", "shreveport", "akron", "aurora",
    "yonkers", "glendale", "huntington beach", "grand rapids",
    "salt lake city", "tallahassee", "huntsville", "worcester",
    "knoxville", "providence", "moreno valley", "little rock",
    "augusta", "oxnard", "tempe", "overland park", "sioux falls",
    "cape coral", "santa clara",
    "columbia", "fort lauderdale", "chattanooga", "brownsville",
    "aurora", "elk grove", "springfield", "peoria", "clarksville",
    "sunnyvale", "garden grove", "oceanside", "santa rosa",
    "rancho cucamonga", "mckinney", "laredo", "frisco", "hayward",
    "pomona", "palmdale", "escondido", "torrance", "pasadena",
    "bridgeport", "sterling heights", "paterson", "surprise",
    "denton", "roseville", "macon", "corona", "killeen",
    "kansas city", "new haven", "savannah", "hartford", "rockford",
    "jackson", "bellevue", "alexandria", "sunnyvale",
    "bay area", "silicon valley", "research triangle",
})

_US_STATE_ABBREVS = frozenset({
    "AL", "AK", "AZ", "AR", "CA", "CO", "CT", "DE", "FL", "GA",
    "HI", "ID", "IL", "IN", "IA", "KS", "KY", "LA", "ME", "MD",
    "MA", "MI", "MN", "MS", "MO", "MT", "NE", "NV", "NH", "NJ",
    "NM", "NY", "NC", "ND", "OH", "OK", "OR", "PA", "RI", "SC",
    "SD", "TN", "TX", "UT", "VT", "VA", "WA", "WV", "WI", "WY", "DC",
})


_NON_US_OVERRIDES = frozenset({
    # Regional catch-alls
    "homeoffice", "emea", "apac", "latam", "worldwide", "global",
    # Country names — checked before "remote" so "Remote - Canada" etc. are rejected
    "canada", "united kingdom", "australia", "germany", "france",
    "netherlands", "switzerland", "ireland", "new zealand", "singapore",
    "hong kong", "south korea", "india", "brazil", "mexico",
    "spain", "italy", "portugal", "poland", "sweden", "norway",
    "denmark", "finland", "austria", "belgium", "ukraine", "japan",
    "china", "taiwan", "indonesia", "malaysia", "thailand", "philippines",
    "pakistan", "nigeria", "kenya", "south africa", "egypt", "turkey",
    "israel", "uae", "czech republic", "vietnam",
    # "UK" as a standalone token (with surrounding punctuation to avoid false positives)
    "- uk", " uk,", " uk)", "/uk", " uk ",
})


def _is_us_location(location: str) -> bool:
    """Return True if the location string appears to be US-based."""
    loc_lower = location.strip().lower()

    # Hard-disqualify non-US patterns before checking US indicators
    for override in _NON_US_OVERRIDES:
        if override in loc_lower:
            return False

    # Check for any US indicator substring
    for indicator in _US_INDICATORS:
        if indicator in loc_lower:
            return True

    # Check comma/pipe/slash-separated tokens for 2-letter state abbreviations
    # e.g. "Chicago, IL" → tokens = ["Chicago", "IL"] → "IL" in abbrevs → True
    tokens = [t.strip() for t in re.split(r"[,/|]", location)]
    for token in tokens:
        if token.strip().upper() in _US_STATE_ABBREVS:
            return True

    return False


# ---------------------------------------------------------------------------
# 1. Keyword scoring
# ---------------------------------------------------------------------------

def score(job: Job, cfg: dict) -> float:
    """
    Returns a relevance score 0–100 for a job against the user's config.
    Higher = better match.
    """
    text = f"{job.title} {job.description} {job.company}".lower()
    title_lower = job.title.lower()
    total = 0.0

    # --- Hard negative filter (title) ---
    neg_keywords = [k.lower() for k in cfg.get("negative_title_keywords", [])]
    for kw in neg_keywords:
        if re.search(r"\b" + re.escape(kw) + r"\b", title_lower):
            return -1.0  # Disqualify entirely

    # --- Negative company filter ---
    company_lower = job.company.lower()
    for co in cfg.get("negative_companies", []):
        if co.lower() in company_lower:
            return -1.0

    # --- Negative description keyword filter ---
    desc_lower = (job.description or "").lower()
    for kw in cfg.get("negative_description_keywords", []):
        if kw.lower() in desc_lower:
            return -1.0

    # --- Location filter (US only) ---
    loc_cfg = cfg.get("location_filter", {})
    if loc_cfg.get("us_only"):
        # Whitelist approach: if a location is set, it must be recognizably US.
        # Empty/None location → allow (can't determine; most ATS entries are US companies).
        if job.location and not _is_us_location(job.location):
            return -1.0
        # Also check description for work-auth language that signals non-US hiring
        if job.description:
            for phrase in ("right to work in the uk", "right to work in the eu",
                           "work authorisation", "work authorisation in",
                           "eligible to work in germany", "eligible to work in australia",
                           "eligible to work in canada"):
                if phrase in desc_lower:
                    return -1.0

    # --- Title keyword boosts ---
    title_cfg = cfg.get("title_keywords", {})
    for kw in title_cfg.get("tier1", []):
        if kw.lower() in title_lower:
            total += 30
    for kw in title_cfg.get("tier2", []):
        if kw.lower() in title_lower:
            total += 15
    for kw in title_cfg.get("tier3", []):
        if kw.lower() in title_lower:
            total += 7

    # --- Description keyword boosts ---
    desc_cfg = cfg.get("description_keywords", {})
    for kw in desc_cfg.get("strong", []):
        if kw.lower() in text:
            total += 5
    for kw in desc_cfg.get("moderate", []):
        if kw.lower() in text:
            total += 2

    # --- Preferred org / industry bonus ---
    for org in cfg.get("preferred_orgs", []):
        if org.lower() in text:
            total += 4
            break  # Only count once

    # --- Remote bonus (small) ---
    if job.remote:
        total += 3

    # --- Experience level penalties (graduated) ---
    # Applied after keyword scoring so bonuses still inform ranking even for over-experienced jobs.
    # hard_disqualify_years (default 10): instant reject
    # heavy_penalty_years (default 7): -50 pts (very unlikely to surface)
    # steep_penalty_years (default 5): -25 pts (may still surface if otherwise strong match)
    if job.description:
        exp_cfg = cfg.get("experience_filter", {})
        hard_yrs   = exp_cfg.get("hard_disqualify_years", 10)
        heavy_yrs  = exp_cfg.get("heavy_penalty_years", 7)
        steep_yrs  = exp_cfg.get("steep_penalty_years", 5)
        desc = job.description
        if hard_yrs > 0 and _exp_re(hard_yrs).search(desc):
            return -1.0
        elif heavy_yrs > 0 and _exp_re(heavy_yrs).search(desc):
            total -= 50
        elif steep_yrs > 0 and _exp_re(steep_yrs).search(desc):
            total -= 25

    return min(total, 100.0)


def filter_and_rank(jobs: list[Job], cfg: dict) -> list[Job]:
    """Score all jobs, drop negatives and below threshold, return sorted list."""
    min_score = cfg.get("digest", {}).get("min_score", 10)
    for job in jobs:
        job.score = score(job, cfg)

    ranked = [j for j in jobs if j.score >= min_score]
    ranked.sort(key=lambda j: j.score, reverse=True)
    return ranked


# ---------------------------------------------------------------------------
# 2. Claude Haiku "why you'd be a fit" explanations
# ---------------------------------------------------------------------------

SYSTEM_PROMPT = """You are a career coach helping a job seeker evaluate whether a role is a good fit.
Be concise, honest, and specific. Do not use generic filler phrases."""

def _match_prompt(job: Job, profile_summary: str) -> str:
    return f"""Here is a job posting:

Title: {job.title}
Company: {job.company}
Location: {job.location}
Description:
{job.description[:2000]}

Here is the candidate's background:
{profile_summary}

In 2-3 sentences, explain specifically why this candidate would be a strong fit for this role.
Reference concrete skills or experience from their background that map to the job requirements.
If the fit is weak, say so briefly. Be direct."""


def add_match_explanations(jobs: list[Job], cfg: dict) -> list[Job]:
    """
    For each job in the list, call Claude Haiku to generate a match explanation.
    Modifies jobs in-place. Falls back to a keyword summary if Claude is unavailable.
    """
    api_key = os.environ.get("ANTHROPIC_API_KEY", "")
    profile = cfg.get("profile", {}).get("summary", "")

    if not api_key or not _CLAUDE_AVAILABLE or not profile:
        # Fallback: generate a simple keyword-based reason
        for job in jobs:
            job.match_reason = _keyword_fallback(job, cfg)
        return jobs

    client = anthropic.Anthropic(api_key=api_key)

    for job in jobs:
        try:
            msg = client.messages.create(
                model="claude-haiku-4-5-20251001",
                max_tokens=200,
                system=SYSTEM_PROMPT,
                messages=[{"role": "user", "content": _match_prompt(job, profile)}],
            )
            job.match_reason = msg.content[0].text.strip()
        except Exception as e:
            print(f"[matcher] Claude error for '{job.title}': {e}")
            job.match_reason = _keyword_fallback(job, cfg)

    return jobs


def _keyword_fallback(job: Job, cfg: dict) -> str:
    """Simple fallback when Claude is unavailable."""
    hits = []
    text = f"{job.title} {job.description}".lower()
    for kw in cfg.get("description_keywords", {}).get("strong", []):
        if kw.lower() in text:
            hits.append(kw)
    if hits:
        return f"Matches your profile on: {', '.join(hits[:5])}."
    return "Title and description overlap with your target roles."
