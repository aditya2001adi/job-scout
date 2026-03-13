"""
ATS scraper — Greenhouse, Ashby, and iCIMS.

Reads job_boards.csv (Company, Industry, ATS, URL) and fetches all job listings
from each company's career page using the respective ATS API or HTML scraper.

APIs used:
  Greenhouse: https://boards-api.greenhouse.io/v1/boards/{slug}/jobs?content=true
  Ashby:      https://api.ashbyhq.com/posting-api/job-board/{slug}
  iCIMS:      HTML scraping via ?ss=1&in_iframe=1 (no public JSON API exists)
"""
import csv
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Optional

import requests
from bs4 import BeautifulSoup
from scrapers.base import Job

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                  "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0.0.0 Safari/537.36",
    "Accept": "application/json",
}

CSV_PATH = Path(__file__).parent.parent / "job_boards.csv"


def _strip_html(html: str) -> str:
    """Strip HTML tags and return plain text, truncated to 3000 chars."""
    if not html:
        return ""
    return BeautifulSoup(html, "html.parser").get_text(separator=" ", strip=True)[:3000]


def _parse_dt(s: str) -> Optional[datetime]:
    """Parse an ISO 8601 datetime string to a UTC-aware datetime."""
    if not s:
        return None
    try:
        return datetime.fromisoformat(s.replace("Z", "+00:00"))
    except ValueError:
        return None


def _scrape_greenhouse(slug: str, company_name: str, cutoff: Optional[datetime],
                       seen_urls: set, session: requests.Session) -> list[Job]:
    """Fetch all jobs from a Greenhouse board."""
    url = f"https://boards-api.greenhouse.io/v1/boards/{slug}/jobs?content=true"
    try:
        resp = session.get(url, timeout=15)
        if resp.status_code == 404:
            # Company may have moved off Greenhouse or slug changed
            return []
        if resp.status_code != 200:
            print(f"[ats/greenhouse] {company_name}: HTTP {resp.status_code}")
            return []
        raw_jobs = resp.json().get("jobs", [])
    except Exception as e:
        print(f"[ats/greenhouse] {company_name}: {e}")
        return []

    result = []
    for raw in raw_jobs:
        job_url = raw.get("absolute_url", "")
        if not job_url or job_url in seen_urls:
            continue

        # Date filter
        if cutoff is not None:
            updated = _parse_dt(raw.get("updated_at", ""))
            if updated is not None and updated < cutoff:
                continue
            # If updated is None (missing/unparseable), include the job

        seen_urls.add(job_url)
        title = raw.get("title", "").strip()
        if not title:
            continue

        location = (raw.get("location") or {}).get("name", "")
        remote = "remote" in (location + title).lower()
        desc = _strip_html(raw.get("content", ""))
        posted = (raw.get("updated_at") or "")[:10]

        result.append(Job(
            title=title,
            company=company_name,
            location=location,
            url=job_url,
            description=desc,
            source="ats_greenhouse",
            posted_date=posted,
            remote=remote,
        ))

    return result


def _scrape_ashby(slug: str, company_name: str, cutoff: Optional[datetime],
                  seen_urls: set, session: requests.Session) -> list[Job]:
    """Fetch all jobs from an Ashby board."""
    url = f"https://api.ashbyhq.com/posting-api/job-board/{slug}"
    try:
        resp = session.get(url, timeout=15)
        if resp.status_code == 404:
            return []
        if resp.status_code != 200:
            print(f"[ats/ashby] {company_name}: HTTP {resp.status_code}")
            return []
        raw_jobs = resp.json().get("jobs", [])
    except Exception as e:
        print(f"[ats/ashby] {company_name}: {e}")
        return []

    result = []
    for raw in raw_jobs:
        job_url = raw.get("jobUrl", "")
        if not job_url or job_url in seen_urls:
            continue

        # Date filter
        if cutoff is not None:
            published = _parse_dt(raw.get("publishedAt", ""))
            if published is not None and published < cutoff:
                continue

        seen_urls.add(job_url)
        title = raw.get("title", "").strip()
        if not title:
            continue

        # Ashby location can be a string or an object
        location_raw = raw.get("location", "")
        if isinstance(location_raw, dict):
            location = location_raw.get("locationName", "") or location_raw.get("name", "")
        else:
            location = str(location_raw)

        remote = raw.get("isRemote", False) or "remote" in (location + title).lower()
        desc = _strip_html(raw.get("descriptionHtml", ""))
        posted = (raw.get("publishedAt") or "")[:10]

        result.append(Job(
            title=title,
            company=company_name,
            location=location,
            url=job_url,
            description=desc,
            source="ats_ashby",
            posted_date=posted,
            remote=remote,
        ))

    return result


def _normalize_icims_location(loc: str) -> str:
    """Convert iCIMS internal location codes to human-readable form.

    iCIMS often returns locations like 'US-TN-Nashville' instead of 'Nashville, TN'.
    """
    if loc.startswith("US-") and "-" in loc[3:]:
        parts = loc.split("-")
        # "US-TN-Nashville" → "Nashville, TN"
        # "US-TN-Nashville-Some-Suburb" → "Nashville-Some-Suburb, TN"
        state = parts[1]
        city = "-".join(parts[2:])
        return f"{city}, {state}" if city else state
    return loc


def _scrape_icims(base_url: str, company_name: str, seen_urls: set,
                  session: requests.Session) -> list[Job]:
    """
    Fetch jobs from an iCIMS board via HTML scraping.

    iCIMS has no public JSON API. The ?in_iframe=1 param bypasses the JS wrapper
    and returns fully server-rendered HTML with consistent class names across all
    iCIMS clients. Paginated with &pr=N (0-indexed page offset).

    Note: iCIMS listing pages include only a short description snippet. Full
    descriptions would require one extra request per job — skipped here for speed.
    Title + location + snippet are enough for keyword scoring on these companies.
    """
    search_base = base_url.rstrip("/") + "/search?ss=1&in_iframe=1"
    jobs = []
    page = 0

    while True:
        url = search_base + (f"&pr={page}" if page > 0 else "")
        try:
            resp = session.get(url, timeout=15)
            if resp.status_code != 200:
                if page == 0:
                    print(f"[ats/icims] {company_name}: HTTP {resp.status_code}")
                break
        except Exception as e:
            if page == 0:
                print(f"[ats/icims] {company_name}: {e}")
            break

        soup = BeautifulSoup(resp.text, "html.parser")
        table = soup.find("div", class_="iCIMS_JobsTable")
        if not table:
            break

        found_any = False
        for row in table.find_all("div", class_="row"):
            title_div = row.find("div", class_="title")
            if not title_div:
                continue
            a = title_div.find("a")
            if not a:
                continue
            h3 = a.find("h3")
            title = h3.get_text(strip=True) if h3 else a.get_text(strip=True)
            if not title:
                continue

            # Strip in_iframe param for a clean canonical URL
            job_url = a.get("href", "").replace("?in_iframe=1", "").replace("&in_iframe=1", "")
            if not job_url or job_url in seen_urls:
                continue
            seen_urls.add(job_url)
            found_any = True

            # Location: iCIMS uses "US-TN-Nashville" codes on some boards
            loc_div = row.find("div", class_="header")
            if loc_div:
                spans = loc_div.find_all("span")
                raw_loc = spans[-1].get_text(strip=True) if spans else ""
                location = _normalize_icims_location(raw_loc)
            else:
                location = ""

            # Short description snippet available on the listing page
            desc_div = row.find("div", class_="description")
            snippet = desc_div.get_text(separator=" ", strip=True) if desc_div else ""

            remote = "remote" in (location + title + snippet).lower()

            jobs.append(Job(
                title=title,
                company=company_name,
                location=location,
                url=job_url,
                description=snippet,
                source="ats_icims",
                posted_date="",
                remote=remote,
            ))

        if not found_any:
            break

        # Advance to next page if available
        if not soup.find("link", rel="next"):
            break
        page += 1
        time.sleep(0.1)

    return jobs


def scrape(cfg: dict, no_date_filter: bool = False) -> list[Job]:
    """
    Scrape all companies in job_boards.csv via Greenhouse or Ashby.
    Returns a list of Job objects. Applies date filter unless no_date_filter=True.
    """
    if not CSV_PATH.exists():
        print(f"[ats] job_boards.csv not found at {CSV_PATH}")
        return []

    # Compute date cutoff
    cutoff: Optional[datetime] = None
    if not no_date_filter:
        days = cfg.get("date_filter", {}).get("days", 7)
        cutoff = datetime.now(timezone.utc) - timedelta(days=days)

    # Read companies
    companies = []
    with open(CSV_PATH, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            companies.append(row)

    days_label = "no date filter" if no_date_filter else f"last {cfg.get('date_filter', {}).get('days', 7)} days"
    print(f"[ats] Scraping {len(companies)} companies ({days_label})...")

    session = requests.Session()
    session.headers.update(HEADERS)

    jobs: list[Job] = []
    seen_urls: set = set()
    gh_count = 0
    ashby_count = 0
    icims_count = 0

    for company in companies:
        name = company.get("Company", "").strip()
        ats = company.get("ATS", "").strip().lower()
        url = company.get("URL", "").strip()

        if not url:
            continue

        if ats == "greenhouse":
            slug = url.rstrip("/").split("/")[-1]
            new_jobs = _scrape_greenhouse(slug, name, cutoff, seen_urls, session)
            gh_count += 1
        elif ats == "ashby":
            slug = url.rstrip("/").split("/")[-1]
            new_jobs = _scrape_ashby(slug, name, cutoff, seen_urls, session)
            ashby_count += 1
        elif ats == "icims":
            # iCIMS: pass the full URL — no date filter available (no timestamp field)
            new_jobs = _scrape_icims(url, name, seen_urls, session)
            icims_count += 1
        else:
            print(f"[ats] Unknown ATS type '{ats}' for {name} — skipping")
            continue

        jobs.extend(new_jobs)
        time.sleep(0.1)  # polite delay

    print(f"[ats] Done. {gh_count} Greenhouse + {ashby_count} Ashby + {icims_count} iCIMS companies → {len(jobs)} jobs")
    return jobs
