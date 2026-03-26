# CLAUDE.md — Job Scout

## Project Goal
Automated daily job digest tool focused on **renewable energy and construction**. Scrapes Greenhouse/Ashby job boards at targeted cleantech and construction companies, scores matches against Adi's background, and emails 5-7 relevant jobs each morning. Target roles: Strategy & Operations, Chief of Staff, Program Manager at companies working in solar, wind, BESS, EV charging, green materials, energy software, and large-scale/residential construction. Target: spend less time browsing, more time applying.

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
├── job_boards.csv           # 33 verified energy/construction companies (Greenhouse + Ashby)
├── matcher.py               # Keyword scoring (0-100) + Claude Haiku match explanations
├── dedup.py                 # SQLite seen-jobs tracker (jobs.db, gitignored)
├── emailer.py               # Resend API email sender
├── scrapers/
│   ├── base.py              # Job dataclass
│   ├── hiring_cafe.py       # hiring.cafe JSON API (currently 429ing — skip for now)
│   ├── progressive_data.py  # progressivedatajobs.org (working, ~12 jobs/run)
│   └── ats.py               # Greenhouse + Ashby ATS APIs (33 companies, energy/construction focused)
├── probe_companies.py       # Discovery script: tests GH/Ashby endpoints for candidate companies
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
- **Primary focus:** Renewable energy (solar, wind, BESS, EV charging, energy software, green materials) and construction (large GC, residential homebuilders, infrastructure)
- **Also interested in:** Adjacent climate tech, carbon management, home efficiency, home services
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
| ATS (Greenhouse + Ashby) | ✅ Working | 33 energy/construction companies, targeted job pool |
| Hiring Cafe | ❌ 429 blocked | Both homepage and API return 429 from all IPs tried |

## Dedup Behavior
- `dedup.mark_seen()` marks ALL scored new jobs (not just top N sent) as seen after each run
- This means: on first run with `--no-date-filter`, all 7K+ scored jobs are seeded to DB
- Going forward: only jobs that are BOTH new (posted in last 7 days) AND not in dedup DB surface

## Expanding the Company List
- Run `python3 probe_companies.py --output` to re-probe and regenerate job_boards.csv
- Add new candidates to the `CANDIDATES` list in `probe_companies.py` with slug guesses
- Most large GCs and homebuilders use Workday/iCIMS — adding iCIMS scraper support is the path to broader construction coverage
- Probe findings: 223 companies tested, 13.5% hit rate; GCs/homebuilders were ~0% on GH/Ashby

## Next Steps (priority order)

### 1. ✅ Narrowed focus to energy/construction
- Replaced 169-company general list with 33 verified renewable energy + construction companies
- Scoring keywords tuned based on 89-job application history

### 2. ✅ GitHub automation live
- Repo: github.com/aditya2001adi/job-scout
- GitHub Actions runs daily at 8am CDT, emails results, commits dedup DB back

### 3. Seed dedup DB after company list change
- Run `--no-date-filter` once to re-seed so old jobs from new companies don't flood the digest

### 4. Enable Claude Haiku match explanations
- Works already — just remove `--no-claude` flag from daily.yml
- Cost: ~$1/month (7 calls/day × 2K tokens at Haiku pricing)
- Requires `ANTHROPIC_API_KEY` as GitHub Actions secret

### 5. Expand company list
- Add more cleantech companies as they are identified
- Consider iCIMS scraper support for construction GCs (Turner, McCarthy, DPR, etc.)

## API Keys (reference — do not commit)
- **Resend:** stored as `RESEND_API_KEY` env var
- **Anthropic:** stored as `ANTHROPIC_API_KEY` env var
- **FEC/data.gov:** `vVmdRH3fu1pJlyM3CZlbPLtstv0UFemMtNGCEEBR` (for future use)
