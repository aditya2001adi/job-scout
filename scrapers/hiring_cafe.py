"""
Hiring Cafe scraper — uses their internal JSON API.
No Playwright needed; standard requests with browser-like headers.
"""
import time
import requests
from typing import Any, Optional
from scrapers.base import Job

# These headers mimic a real browser request. Required — bare requests get 429.
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                  "AppleWebKit/537.36 (KHTML, like Gecko) "
                  "Chrome/130.0.0.0 Safari/537.36",
    "Accept": "application/json, text/plain, */*",
    "Accept-Language": "en-US,en;q=0.9",
    "Accept-Encoding": "gzip, deflate, br",
    "Content-Type": "application/json",
    "Referer": "https://hiring.cafe/",
    "Origin": "https://hiring.cafe",
    "sec-ch-ua": '"Chromium";v="130", "Not;A=Brand";v="99"',
    "sec-ch-ua-mobile": "?0",
    "sec-ch-ua-platform": '"macOS"',
    "Sec-Fetch-Dest": "empty",
    "Sec-Fetch-Mode": "cors",
    "Sec-Fetch-Site": "same-origin",
}

BASE_URL = "https://hiring.cafe"
JOBS_ENDPOINT = f"{BASE_URL}/api/search-jobs"
COUNT_ENDPOINT = f"{BASE_URL}/api/search-jobs/get-total-count"


def _build_search_state(query: str, cfg: dict) -> dict:
    hc_cfg = cfg.get("hiring_cafe", {})
    workplace_types = hc_cfg.get("workplace_types", ["Remote", "Hybrid", "Onsite"])
    seniority = hc_cfg.get("seniority", ["Entry Level", "Mid Level"])
    commitment_types = hc_cfg.get("commitment_types", ["Full Time"])
    days = hc_cfg.get("date_posted_days", 7)

    return {
        "locations": [
            {
                "formatted_address": "United States",
                "types": ["country"],
                "geometry": {"location": {"lat": "39.8283", "lon": "-98.5795"}},
                "id": "user_country",
                "address_components": [
                    {"long_name": "United States", "short_name": "US", "types": ["country"]}
                ],
                "options": {"flexible_regions": ["anywhere_in_continent", "anywhere_in_world"]},
            }
        ],
        "workplaceTypes": workplace_types,
        "defaultToUserLocation": False,
        "userLocation": None,
        "commitmentTypes": commitment_types,
        "seniorityLevel": seniority,
        "searchQuery": query,
        "dateFetchedPastNDays": days,
        # --- Permissive defaults for everything else ---
        "physicalEnvironments": ["Office", "Outdoor", "Vehicle", "Industrial", "Customer-Facing"],
        "physicalLaborIntensity": ["Low", "Medium", "High"],
        "physicalPositions": ["Sitting", "Standing"],
        "oralCommunicationLevels": ["Low", "Medium", "High"],
        "computerUsageLevels": ["Low", "Medium", "High"],
        "cognitiveDemandLevels": ["Low", "Medium", "High"],
        "currency": {"label": "Any", "value": None},
        "frequency": {"label": "Any", "value": None},
        "minCompensationLowEnd": None,
        "minCompensationHighEnd": None,
        "maxCompensationLowEnd": None,
        "maxCompensationHighEnd": None,
        "restrictJobsToTransparentSalaries": False,
        "calcFrequency": "Yearly",
        "roleTypes": ["Individual Contributor", "People Manager"],
        "roleYoeRange": [0, 20],
        "excludeIfRoleYoeIsNotSpecified": False,
        "managementYoeRange": [0, 20],
        "excludeIfManagementYoeIsNotSpecified": False,
        "securityClearances": [
            "None", "Confidential", "Secret", "Top Secret",
            "Top Secret/SCI", "Public Trust", "Interim Clearances", "Other"
        ],
        "languageRequirements": [],
        "excludedLanguageRequirements": [],
        "languageRequirementsOperator": "OR",
        "excludeJobsWithAdditionalLanguageRequirements": False,
        "airTravelRequirement": ["None", "Minimal", "Moderate", "Extensive"],
        "landTravelRequirement": ["None", "Minimal", "Moderate", "Extensive"],
        "weekendAvailabilityRequired": "Doesn't Matter",
        "holidayAvailabilityRequired": "Doesn't Matter",
        "overtimeRequired": "Doesn't Matter",
        "onCallRequirements": ["None", "Occasional (once a month or less)", "Regular (once a week or more)"],
        "benefitsAndPerks": [],
        "applicationFormEase": [],
        "companyNames": [],
        "excludedCompanyNames": [],
        "usaGovPref": None,
        "industries": [],
        "excludedIndustries": [],
        "companyKeywords": [],
        "companyKeywordsBooleanOperator": "OR",
        "excludedCompanyKeywords": [],
        "hideJobTypes": [],
        "encouragedToApply": [],
        "hiddenCompanies": [],
        "user": None,
        "searchModeSelectedCompany": None,
        "departments": [],
        "restrictedSearchAttributes": [],
        "sortBy": "default",
        "technologyKeywordsQuery": "",
        "requirementsKeywordsQuery": "",
        "jobTitleQuery": "",
        "jobDescriptionQuery": "",
        "companyPublicOrPrivate": "all",
        "latestInvestmentYearRange": [None, None],
        "latestInvestmentSeries": [],
        "latestInvestmentAmount": None,
        "latestInvestmentCurrency": [],
        "investors": [],
        "excludedInvestors": [],
        "isNonProfit": "all",
        "companySizeRanges": [],
        "minYearFounded": None,
        "maxYearFounded": None,
        "excludedLatestInvestmentSeries": [],
    }


def _parse_job(raw: dict) -> Optional[Job]:
    """Convert a raw Hiring Cafe API job dict to a Job object."""
    try:
        title = raw.get("jobTitle") or raw.get("title") or ""
        company = (raw.get("company") or {}).get("name") or raw.get("companyName") or ""
        url = raw.get("jobPostingUrl") or raw.get("url") or ""
        if not url:
            return None

        # Location
        loc_parts = []
        loc = raw.get("location") or {}
        if isinstance(loc, dict):
            city = loc.get("city") or ""
            state = loc.get("state") or ""
            if city:
                loc_parts.append(city)
            if state:
                loc_parts.append(state)
        elif isinstance(loc, str):
            loc_parts.append(loc)
        location = ", ".join(loc_parts) if loc_parts else "Unknown"

        # Remote flag
        workplace = (raw.get("workplaceType") or "").lower()
        remote = "remote" in workplace

        # Description — Hiring Cafe returns structured description fields
        desc_parts = []
        if raw.get("jobDescription"):
            desc_parts.append(raw["jobDescription"])
        if raw.get("jobRequirements"):
            desc_parts.append("Requirements: " + raw["jobRequirements"])
        description = "\n\n".join(desc_parts)[:3000]  # cap at 3K chars

        # Salary
        salary = None
        comp = raw.get("compensation") or {}
        if isinstance(comp, dict):
            low = comp.get("lowEnd")
            high = comp.get("highEnd")
            freq = comp.get("frequency") or ""
            currency = comp.get("currency") or "USD"
            if low and high:
                salary = f"{currency} {low:,}–{high:,} {freq}".strip()
            elif low:
                salary = f"{currency} {low:,}+ {freq}".strip()

        posted = raw.get("dateFetched") or raw.get("postedDate") or None

        return Job(
            title=title,
            company=company,
            location=location,
            url=url,
            description=description,
            source="hiring_cafe",
            posted_date=posted,
            salary=salary,
            remote=remote,
        )
    except Exception:
        return None


def scrape(cfg: dict) -> "list[Job]":
    """
    Run all configured Hiring Cafe search queries and return deduplicated Job list.
    """
    queries = cfg.get("hiring_cafe", {}).get("queries", ["strategy operations"])
    seen_urls: set[str] = set()
    jobs: list[Job] = []

    session = requests.Session()
    session.headers.update(HEADERS)

    for i, query in enumerate(queries):
        if i > 0:
            time.sleep(1.5)  # polite delay between queries

        search_state = _build_search_state(query, cfg)
        payload = {"searchState": search_state, "page": 1, "pageSize": 1000}

        try:
            resp = session.post(JOBS_ENDPOINT, json=payload, timeout=30)
            if resp.status_code != 200:
                print(f"[hiring_cafe] Query '{query}' → HTTP {resp.status_code}")
                continue

            data = resp.json()

            # Extract the jobs list from the response
            raw_jobs: list[dict[str, Any]] = []
            if isinstance(data, list):
                raw_jobs = data
            elif isinstance(data, dict):
                for key in ("results", "jobs", "data", "items", "content"):
                    if key in data and isinstance(data[key], list):
                        raw_jobs = data[key]
                        break
                if not raw_jobs and "hits" in data:
                    hits = data["hits"]
                    if isinstance(hits, dict) and "hits" in hits:
                        raw_jobs = [h.get("_source", h) for h in hits["hits"]]

            new_count = 0
            for raw in raw_jobs:
                job = _parse_job(raw)
                if job and job.url not in seen_urls:
                    seen_urls.add(job.url)
                    jobs.append(job)
                    new_count += 1

            print(f"[hiring_cafe] '{query}' → {new_count} jobs")

        except requests.RequestException as e:
            print(f"[hiring_cafe] Request error for '{query}': {e}")
        except Exception as e:
            print(f"[hiring_cafe] Parse error for '{query}': {e}")

    print(f"[hiring_cafe] Total unique jobs: {len(jobs)}")
    return jobs
