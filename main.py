#!/usr/bin/env python3
"""
Job Scout — daily job digest orchestrator.

Usage:
  python3 main.py                  # Full run: scrape → filter → email
  python3 main.py --dry-run        # Print results, don't send email or mark seen
  python3 main.py --no-claude      # Skip Claude Haiku explanations
  python3 main.py --source hc      # Only run hiring_cafe scraper (hc / pdj)
"""
import argparse
import sys
from pathlib import Path

import yaml

import dedup
import matcher
import emailer
from scrapers import hiring_cafe, progressive_data, ats


def load_config() -> dict:
    cfg_path = Path(__file__).parent / "config.yaml"
    with open(cfg_path) as f:
        return yaml.safe_load(f)


def run(dry_run: bool = False, no_claude: bool = False, sources=None, no_date_filter: bool = False):
    cfg = load_config()
    digest_cfg = cfg.get("digest", {})
    max_jobs = digest_cfg.get("max_jobs", 7)
    max_per_company = digest_cfg.get("max_per_company", 0)  # 0 = no cap

    print("=" * 60)
    print("Job Scout starting up")
    print(f"  dry_run={dry_run}  no_claude={no_claude}  sources={sources or 'all'}  no_date_filter={no_date_filter}")
    print("=" * 60)

    # ── 1. Scrape ──────────────────────────────────────────────
    all_jobs = []

    run_all = not sources
    run_hc = run_all or "hc" in (sources or [])
    run_pdj = run_all or "pdj" in (sources or [])
    run_ats = run_all or "ats" in (sources or [])

    if run_hc:
        print("\n[1/4] Scraping Hiring Cafe...")
        hc_jobs = hiring_cafe.scrape(cfg)
        all_jobs.extend(hc_jobs)

    if run_pdj:
        print("\n[1/4] Scraping Progressive Data Jobs...")
        all_jobs.extend(progressive_data.scrape(cfg, no_date_filter=no_date_filter))

    if run_ats:
        print("\n[1/4] Scraping ATS company boards (Greenhouse + Ashby)...")
        all_jobs.extend(ats.scrape(cfg, no_date_filter=no_date_filter))

    print(f"\n  Total scraped: {len(all_jobs)} jobs")

    # ── 2. Filter & rank ───────────────────────────────────────
    print("\n[2/4] Scoring and filtering...")
    ranked = matcher.filter_and_rank(all_jobs, cfg)
    print(f"  After scoring: {len(ranked)} jobs above threshold")

    # ── 2b. Deduplicate same-title/company across locations ────
    # Normalize titles before comparing so "Strategy Associate - New York" and
    # "Strategy Associate - San Francisco" collapse to the same key.
    # Key is always (normalized_title, company) — same title at different companies is fine.
    import re as _re
    def _normalize_title(t: str) -> str:
        # Strip trailing " - Location", " | Location" suffixes (capital-letter hint)
        t = _re.sub(r'\s*[-–|]\s*[A-Z][^-–|]{1,40}$', '', t)
        # Strip trailing parentheticals like " (Remote)" or " (Chicago, IL)"
        t = _re.sub(r'\s*\([^)]{1,50}\)\s*$', '', t)
        return t.lower().strip()

    seen_title_co: set = set()
    unique_ranked = []
    for job in ranked:
        key = (_normalize_title(job.title), job.company.lower().strip())
        if key not in seen_title_co:
            seen_title_co.add(key)
            unique_ranked.append(job)
    if len(unique_ranked) < len(ranked):
        print(f"  Removed {len(ranked) - len(unique_ranked)} duplicate title+company listings")
    ranked = unique_ranked

    # ── 3. Dedup ───────────────────────────────────────────────
    print("\n[3/4] Deduplicating...")
    new_jobs = dedup.filter_new(ranked)
    print(f"  New jobs (not seen before): {len(new_jobs)}")
    print(f"  Total jobs ever seen: {dedup.seen_count()}")

    # ── 4. Take top N & generate match explanations ────────────
    # Apply per-company cap before selecting top N
    if max_per_company > 0:
        company_counts: dict = {}
        capped: list = []
        for job in new_jobs:
            n = company_counts.get(job.company, 0)
            if n < max_per_company:
                capped.append(job)
                company_counts[job.company] = n + 1
        new_jobs = capped

    top_jobs = new_jobs[:max_jobs]

    if not top_jobs:
        print("\n  No new matching jobs today. No email sent.")
        return

    print(f"\n[4/4] Generating match explanations for {len(top_jobs)} jobs...")
    if no_claude:
        for job in top_jobs:
            job.match_reason = matcher._keyword_fallback(job, cfg)
    else:
        matcher.add_match_explanations(top_jobs, cfg)

    # ── Print summary ──────────────────────────────────────────
    print("\n── Top matches ──────────────────────────────────────────")
    for i, job in enumerate(top_jobs, 1):
        remote_tag = " [REMOTE]" if job.remote else ""
        salary_tag = f" | {job.salary}" if job.salary else ""
        print(f"  {i:2}. [{job.score:4.0f}] {job.title} @ {job.company}{remote_tag}{salary_tag}")
        print(f"       {job.url}")
        if job.match_reason:
            print(f"       → {job.match_reason[:120]}...")

    # ── Send email ─────────────────────────────────────────────
    if dry_run:
        print("\n  [dry-run] Skipping email send and dedup write.")
    else:
        print("\n  Sending email...")
        try:
            emailer.send(top_jobs, cfg)
        except EnvironmentError as e:
            print(f"\n  ERROR: {e}")
            print("  Set BREVO_SMTP_LOGIN and BREVO_SMTP_KEY and re-run.")
            sys.exit(1)

        # Mark all ranked new jobs (not just top N) as seen, so they don't
        # pile up and flood tomorrow's digest.
        dedup.mark_seen(new_jobs)
        print("  Done. Dedup updated.")

    print("\n" + "=" * 60)
    print(f"Job Scout finished. {len(top_jobs)} jobs in today's digest.")
    print("=" * 60)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Job Scout daily digest")
    parser.add_argument("--dry-run", action="store_true",
                        help="Print results without sending email or updating dedup DB")
    parser.add_argument("--no-claude", action="store_true",
                        help="Skip Claude Haiku match explanations")
    parser.add_argument("--source", dest="sources", action="append",
                        choices=["hc", "pdj", "idealist", "builtin", "ats"],
                        help="Run only specific scraper(s) (can repeat)")
    parser.add_argument("--no-date-filter", action="store_true",
                        help="Skip date filter — include all jobs regardless of when posted. "
                             "Use on first run to seed the dedup DB.")
    args = parser.parse_args()

    run(dry_run=args.dry_run, no_claude=args.no_claude, sources=args.sources,
        no_date_filter=args.no_date_filter)
