"""
Base scraper interface. All scrapers return a list of Job objects.
"""
from dataclasses import dataclass, field
from typing import Optional


@dataclass
class Job:
    title: str
    company: str
    location: str
    url: str
    description: str
    source: str                        # e.g. "hiring_cafe", "progressive_data"
    posted_date: Optional[str] = None
    salary: Optional[str] = None
    remote: bool = False
    score: float = 0.0                 # filled in by matcher.py
    match_reason: str = ""             # filled in by matcher.py / Claude

    @property
    def uid(self) -> str:
        """Stable unique ID for dedup (source + url)."""
        return f"{self.source}::{self.url}"

    def __repr__(self):
        return f"<Job {self.title} @ {self.company} [{self.source}]>"
