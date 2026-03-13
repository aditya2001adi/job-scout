"""
Progressive Data Jobs scraper — server-rendered WordPress, no Playwright needed.
Scrapes progressivedatajobs.org for job listings.
"""
import time
from datetime import datetime, timedelta, timezone
from typing import Optional

import requests
from bs4 import BeautifulSoup
from scrapers.base import Job

BASE_URL = "https://www.progressivedatajobs.org"
LISTINGS_URL = f"{BASE_URL}/job-postings/"

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                  "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml",
}


def _fetch_job_detail(session: requests.Session, url: str) -> dict:
    """Fetch and parse a single job detail page. Returns dict of fields."""
    try:
        resp = session.get(url, timeout=15)
        if resp.status_code != 200:
            return {}
        soup = BeautifulSoup(resp.text, "html.parser")
        content = soup.find("div", class_="entry-content")
        if not content:
            return {}

        text = content.get_text(separator="\n", strip=True)

        # Extract structured fields by scanning for label → value pairs
        def _after_label(label: str) -> str:
            """Find the text node immediately after a label string."""
            el = content.find(string=lambda t: t and t.strip() == label)
            if el and el.parent:
                sibling = el.parent.find_next_sibling()
                if sibling:
                    return sibling.get_text(strip=True)
                # Try next text node
                for s in el.parent.next_siblings:
                    t = str(s).strip()
                    if t and t != label:
                        return t
            return ""

        location = _after_label("Location") or ""
        salary = _after_label("Salary Range") or ""
        # Full description: everything after the position summary heading
        desc = ""
        summary_el = content.find(string=lambda t: t and "Position Summary" in t)
        if summary_el:
            # Grab all text from that point on
            parts = []
            node = summary_el.parent
            while node:
                parts.append(node.get_text(separator=" ", strip=True))
                node = node.find_next_sibling()
            desc = "\n".join(parts)[:3000]
        else:
            desc = text[:3000]

        remote = "remote" in text.lower()

        return {"location": location, "salary": salary, "description": desc, "remote": remote}

    except Exception:
        return {}


def scrape(cfg: dict, no_date_filter: bool = False) -> list:
    """Scrape all current listings from Progressive Data Jobs."""
    session = requests.Session()
    session.headers.update(HEADERS)
    jobs = []

    # Compute date cutoff
    cutoff: Optional[datetime] = None
    if not no_date_filter:
        days = cfg.get("date_filter", {}).get("days", 7)
        cutoff = datetime.now(timezone.utc) - timedelta(days=days)

    try:
        resp = session.get(LISTINGS_URL, timeout=20)
        if resp.status_code != 200:
            print(f"[progressive_data] Listings page returned HTTP {resp.status_code}")
            return []

        soup = BeautifulSoup(resp.text, "html.parser")

        # Each job is in a div.grid-job; deduplicate URLs
        seen_urls: set = set()
        containers = soup.find_all("div", class_="grid-job")

        print(f"[progressive_data] Found {len(containers)} listings on page")

        for container in containers:
            # Get the canonical link (first /job-posting/ link that isn't "Learn more")
            link = None
            for a in container.find_all("a", href=True):
                if "/job-posting/" in a["href"] and "learn more" not in a.text.strip().lower():
                    link = a
                    break
            if not link:
                # Fall back to any /job-posting/ link
                link = container.find("a", href=lambda h: h and "/job-posting/" in h)
            if not link:
                continue

            url = link["href"]
            if url in seen_urls:
                continue
            seen_urls.add(url)

            title = link.get_text(strip=True)
            if not title or title.lower() == "learn more →":
                continue

            # Parse listing text: "Posted on Mar 9, 2026 | Title | Company | Learn more →"
            listing_text = container.get_text(separator="|", strip=True)
            parts = [p.strip() for p in listing_text.split("|")]

            company = ""
            posted = ""
            for part in parts:
                if part.startswith("Posted on"):
                    posted = part.replace("Posted on", "").strip()
                elif part and part != title and "learn more" not in part.lower():
                    if not company:
                        company = part

            # Date filter — skip detail page fetch for old jobs (saves HTTP calls)
            if cutoff is not None and posted:
                try:
                    posted_dt = datetime.strptime(posted, "%b %d, %Y").replace(tzinfo=timezone.utc)
                    if posted_dt < cutoff:
                        continue
                except ValueError:
                    pass  # Can't parse date → include the job

            # Fetch detail page for full description, location, salary
            time.sleep(0.5)  # polite delay
            detail = _fetch_job_detail(session, url)

            jobs.append(Job(
                title=title,
                company=company,
                location=detail.get("location", ""),
                url=url,
                description=detail.get("description", ""),
                source="progressive_data",
                posted_date=posted,
                salary=detail.get("salary") or None,
                remote=detail.get("remote", False),
            ))

        print(f"[progressive_data] Scraped {len(jobs)} jobs")

    except requests.RequestException as e:
        print(f"[progressive_data] Request error: {e}")

    return jobs
