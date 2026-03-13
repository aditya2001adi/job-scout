# Job Scout

Automated daily job digest. Scrapes 236 company career pages every morning, scores matches against your profile, and emails you the top 15.

## What it does

1. **Scrapes** three sources every morning:
   - **Greenhouse** — 192 companies (Stripe, Coinbase, OpenAI, etc.)
   - **Ashby** — 27 companies (LangChain, Brex, etc.)
   - **iCIMS** — 17 companies (Richmond American, etc.)
   - **Progressive Data Jobs** — mission-driven orgs

2. **Scores** each job by matching title and description keywords against your profile (defined in `config.yaml`)

3. **Deduplicates** — jobs you've already been emailed never appear again

4. **Emails** the top 15 matches to your inbox via Resend

## Adding companies

Open `job_boards.csv` and add a row:
```
Company Name,Industry,greenhouse,https://boards.greenhouse.io/companyslug
```
ATS options: `greenhouse`, `ashby`, `icims`

## Adjusting what you see

Edit `config.yaml`:
- `title_keywords` — what job titles to boost
- `description_keywords` — what skills/topics to look for
- `negative_title_keywords` — titles to hard-filter out
- `negative_description_keywords` — phrases that disqualify a job
- `digest.max_jobs` — how many jobs per email (default: 15)
- `date_filter.days` — only show jobs posted in last N days (default: 7)

After making changes locally, push to GitHub:
```bash
git add config.yaml job_boards.csv
git commit -m "update keywords"
git push
```
The next morning's run will use the updated config.

## Manual trigger

Go to **Actions** tab on GitHub → **Daily Job Digest** → **Run workflow** to fire it immediately.

## First-time setup (already done)

```bash
# Seed the dedup DB so you don't get flooded on first run
RESEND_API_KEY="..." python3 main.py --source pdj --source ats --no-date-filter --no-claude
```

## Secrets required

| Secret | Where to set |
|--------|-------------|
| `RESEND_API_KEY` | GitHub → Settings → Secrets and variables → Actions |
