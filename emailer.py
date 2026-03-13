"""
Sends the daily job digest email via Resend API.
Requires RESEND_API_KEY environment variable.
Get a free key at resend.com (3,000 emails/month free, no domain needed).
"""
import os
from datetime import date
from scrapers.base import Job

import resend


# ---------------------------------------------------------------------------
# HTML email template
# ---------------------------------------------------------------------------

def _html(jobs: list[Job], cfg: dict) -> str:
    today = date.today().strftime("%B %d, %Y")
    email_cfg = cfg.get("email", {})
    subject_line = email_cfg.get("subject", "Job Scout").format(
        count=len(jobs), date=today
    )

    cards = "\n".join(_job_card(j) for j in jobs)

    return f"""<!DOCTYPE html>
<html>
<head>
<meta charset="utf-8">
<style>
  body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
         background: #f5f5f5; margin: 0; padding: 20px; color: #333; }}
  .container {{ max-width: 700px; margin: 0 auto; }}
  h1 {{ color: #1a1a1a; font-size: 22px; border-bottom: 3px solid #2563eb; padding-bottom: 8px; }}
  .meta {{ color: #666; font-size: 13px; margin-bottom: 24px; }}
  .card {{ background: #fff; border-radius: 8px; border-left: 4px solid #2563eb;
           padding: 18px 20px; margin-bottom: 24px; box-shadow: 0 1px 4px rgba(0,0,0,0.10); }}
  .card h2 {{ margin: 0 0 4px; font-size: 17px; color: #1a1a1a; }}
  .card h2 a {{ color: #2563eb; text-decoration: none; }}
  .card h2 a:hover {{ text-decoration: underline; }}
  .company {{ font-weight: 600; color: #444; font-size: 14px; }}
  .meta-row {{ color: #777; font-size: 13px; margin: 6px 0 10px; }}
  .badge {{ display: inline-block; padding: 2px 8px; border-radius: 12px;
            font-size: 11px; font-weight: 600; margin-right: 6px; }}
  .badge-remote {{ background: #dcfce7; color: #166534; }}
  .badge-source {{ background: #e0e7ff; color: #3730a3; }}
  .badge-salary {{ background: #fef9c3; color: #713f12; }}
  .score-bar {{ height: 4px; background: #e5e7eb; border-radius: 2px; margin: 8px 0; }}
  .score-fill {{ height: 4px; background: #2563eb; border-radius: 2px; }}
  .match {{ background: #eff6ff; border-radius: 6px; padding: 10px 12px;
            font-size: 13px; color: #1e40af; margin-top: 10px; }}
  .match strong {{ display: block; margin-bottom: 3px; font-size: 12px;
                   text-transform: uppercase; letter-spacing: 0.5px; color: #3b82f6; }}
  .footer {{ text-align: center; color: #aaa; font-size: 12px; margin-top: 32px; }}
</style>
</head>
<body>
<div class="container">
  <h1>Job Scout — {len(jobs)} new matches</h1>
  <p class="meta">{today} · Sourced from Hiring Cafe, Progressive Data Jobs, and more</p>
  {cards}
  <div class="footer">
    Job Scout · runs daily at 6am CT via GitHub Actions<br>
    Edit <code>config.yaml</code> to tune keywords and preferences.
  </div>
</div>
</body>
</html>"""


def _job_card(job: Job) -> str:
    score_pct = min(int(job.score), 100)
    score_width = max(score_pct, 5)

    badges = f'<span class="badge badge-source">{job.source.replace("_", " ")}</span>'
    if job.remote:
        badges += '<span class="badge badge-remote">Remote</span>'
    if job.salary:
        badges += f'<span class="badge badge-salary">{job.salary}</span>'

    posted = f" · Posted {job.posted_date}" if job.posted_date else ""
    location = job.location or "Location not listed"

    match_block = ""
    if job.match_reason:
        match_block = f"""
        <div class="match">
          <strong>Why you'd be a fit</strong>
          {job.match_reason}
        </div>"""

    return f"""
<div class="card">
  <h2><a href="{job.url}" target="_blank">{job.title}</a></h2>
  <div class="company">{job.company}</div>
  <div class="meta-row">{location}{posted}</div>
  {badges}
  <div class="score-bar"><div class="score-fill" style="width:{score_width}%"></div></div>
  {match_block}
</div>"""


# ---------------------------------------------------------------------------
# Send
# ---------------------------------------------------------------------------

def send(jobs: list[Job], cfg: dict) -> None:
    """Send the digest email via Resend API (resend.com — free, no domain needed)."""
    api_key = os.environ.get("RESEND_API_KEY", "")
    if not api_key:
        raise EnvironmentError(
            "RESEND_API_KEY environment variable not set.\n"
            "Get a free key at resend.com → API Keys (3,000 emails/month free)."
        )

    resend.api_key = api_key

    email_cfg = cfg.get("email", {})
    to_addr = email_cfg.get("to", "")
    today = date.today().strftime("%B %d, %Y")
    subject = email_cfg.get("subject", "Job Scout: {count} new matches for {date}").format(
        count=len(jobs), date=today
    )

    # Plain-text fallback
    plain_lines = [f"Job Scout — {len(jobs)} new matches for {today}\n"]
    for i, j in enumerate(jobs, 1):
        plain_lines.append(f"{i}. {j.title} @ {j.company} ({j.location})")
        plain_lines.append(f"   {j.url}")
        if j.match_reason:
            plain_lines.append(f"   Why you'd be a fit: {j.match_reason}")
        plain_lines.append("")

    params: resend.Emails.SendParams = {
        "from": "Job Scout <onboarding@resend.dev>",
        "to": [to_addr],
        "subject": subject,
        "html": _html(jobs, cfg),
        "text": "\n".join(plain_lines),
    }

    result = resend.Emails.send(params)
    print(f"[emailer] Sent digest with {len(jobs)} jobs to {to_addr} (id: {result.get('id', '?')})")
