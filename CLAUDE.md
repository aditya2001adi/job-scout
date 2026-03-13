# CLAUDE.md — Job Scout

## Project Goal
Automated daily job digest tool. Scrapes job boards, scores matches against Adi's background, and emails 5-7 relevant jobs each morning. Target: spend less time browsing, more time applying.

## Running Locally
```bash
cd "/Users/adibhalla/Downloads/Job Scout"

# First run — seed dedup DB with all currently available jobs (no date filter)
RESEND_API_KEY="re_..." python3 main.py --source pdj --source ats --no-date-filter --no-claude

# Normal daily run (date filter on, only new jobs)
RESEND_API_KEY="re_..." python3 main.py

# Dry run (print only, no email)
RESEND_API_KEY="re_..." python3 main.py --dry-run --no-claude
```
If dedup blocks results during testing: `rm jobs.db`

## File Structure
```
Job Scout/
├── main.py                  # Orchestrator: scrape → filter → rank → email
├── config.yaml              # Keywords, scoring weights, email settings — edit to tune
├── job_boards.csv           # 226 companies (Greenhouse + Ashby) to scrape
├── matcher.py               # Keyword scoring (0-100) + Claude Haiku match explanations
├── dedup.py                 # SQLite seen-jobs tracker (jobs.db, gitignored)
├── emailer.py               # Resend API email sender
├── scrapers/
│   ├── base.py              # Job dataclass
│   ├── hiring_cafe.py       # hiring.cafe JSON API (currently 429ing — skip for now)
│   ├── progressive_data.py  # progressivedatajobs.org (working, ~12 jobs/run)
│   └── ats.py               # Greenhouse + Ashby ATS APIs (226 companies, ~15K raw jobs)
├── requirements.txt
└── .github/workflows/daily.yml  # GitHub Actions cron (6am CT daily)
```

## Email Setup
- **Service:** Resend (resend.com) — free tier, 3,000 emails/month
- **From:** `Job Scout <onboarding@resend.dev>` (Resend's domain — avoids DKIM/DMARC issues)
- **To:** `aditya2001adi@gmail.com` (Resend free tier restricted to signup email)
- **Env var:** `RESEND_API_KEY` — never hardcode
- Gmail App Passwords not available on Adi's account; Brevo failed DMARC with Gmail sender

## Candidate Profile (for scoring)
- **Background:** L.E.K. Consulting (strategy/due diligence, 13 engagements), Angi (strategy & ops analyst, A/B testing, Looker), Pomona Math+Politics
- **Target roles:** Strategy & Operations, Chief of Staff, Program Manager, consulting-background roles
- **Also interested in:** Progressive/civic/political orgs, industrial companies (construction, housing, energy)
- **Location:** Any major US city or remote
- **Skills:** Python, R, SQL, Excel, Tableau, financial modeling, market sizing

## Date Filter
- Default: only jobs posted/updated in the last 7 days (`config.yaml → date_filter.days`)
- Override: `--no-date-filter` to bypass (use on first run to seed dedup DB)
- ATS: uses `updated_at` (Greenhouse) or `publishedAt` (Ashby) — reliable timestamps
- Progressive Data Jobs: parses "Mar 9, 2026" from listing page

## Active Sources
| Source | Status | Notes |
|--------|--------|-------|
| Progressive Data Jobs | ✅ Working | ~12 jobs/run, progressive/political focus, with date filter |
| ATS (Greenhouse + Ashby) | ✅ Working | 226 companies, ~15K raw jobs, ~7K scored above threshold |
| Hiring Cafe | ❌ 429 blocked | Both homepage and API return 429 from all IPs tried |

## Dedup Behavior
- `dedup.mark_seen()` marks ALL scored new jobs (not just top N sent) as seen after each run
- This means: on first run with `--no-date-filter`, all 7K+ scored jobs are seeded to DB
- Going forward: only jobs that are BOTH new (posted in last 7 days) AND not in dedup DB surface

## Current Scoring Issues (needs tuning)
- Some over-indexing possible: multiple roles from same company (Oscar Health, Stripe) score identically
- Consider adding: per-company cap of 2 jobs in digest to ensure variety
- Consider reweighting: lower Python/SQL description bonus vs strategy/CoS title bonus

## Next Steps (priority order)

### 1. Push to GitHub for automation
- Create private GitHub repo, push all files (including job_boards.csv)
- Add `RESEND_API_KEY` and `ANTHROPIC_API_KEY` as repository secrets
- GitHub Actions will run `main.py` daily at 6am CT via `.github/workflows/daily.yml`
- Note: jobs.db is gitignored — GitHub Actions uses cache to persist it between runs

### 2. ✅ First run complete
- Ran with `--no-date-filter` to seed dedup DB with all currently-available jobs
- Going forward, daily runs surface only new postings (last 7 days, not yet seen)

### 3. Tune scoring
- Add per-company cap (max 2 jobs per company in digest) to ensure variety
- Reweight scoring: strategy/CoS titles tier1=40pts, lower Python/SQL description bonus

### 4. Enable Claude Haiku match explanations
- Works already — just remove `--no-claude` flag
- Cost: ~$1/month (7 calls/day × 2K tokens at Haiku pricing)
- Requires `ANTHROPIC_API_KEY` env var

## API Keys (reference — do not commit)
- **Resend:** stored as `RESEND_API_KEY` env var
- **Anthropic:** stored as `ANTHROPIC_API_KEY` env var
- **FEC/data.gov:** `vVmdRH3fu1pJlyM3CZlbPLtstv0UFemMtNGCEEBR` (for future use)
