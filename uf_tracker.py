#!/usr/bin/env python3
"""
UF Jobs Tracker — explore.jobs.ufl.edu
Scrapes all student assistant / OPS / part-time / temp / FWS positions,
skips already-applied jobs, generates tailored resumes, sends daily email.
"""

import json
import os
import re
import smtplib
import hashlib
import time
import logging
from datetime import datetime
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from pathlib import Path
from urllib.request import urlopen, Request
from urllib.error import URLError, HTTPError

# ── Config ────────────────────────────────────────────────────────────────────

SCRIPT_DIR    = Path(__file__).parent
SEEN_FILE     = SCRIPT_DIR / "uf_seen_jobs.json"
APPLIED_FILE  = SCRIPT_DIR / "uf_applied_jobs.json"
LOG_FILE      = SCRIPT_DIR / "uf_tracker.log"
RESUMES_DIR   = Path("/Users/lokesharora/personal_work/uf_jobs/resumes")

GMAIL_USER       = os.environ.get("GMAIL_USER", "3lokesharora@gmail.com")
GMAIL_APP_PASSWORD = os.environ.get("GMAIL_APP_PASSWORD", "")
RECIPIENT_EMAIL  = os.environ.get("RECIPIENT_EMAIL", "3lokesharora@gmail.com")

# PageUp instance ID 674 = UF
BASE_URL  = "https://careers.pageuppeople.com/674/cw/en-us"
JOB_LINK  = "https://explore.jobs.ufl.edu/cw/en-us/job/{id}/{slug}"

# Job types Lokesh wants — must match at least one (whole-phrase match in title)
TARGET_KEYWORDS = [
    "student assistant", "student aide", "student worker",
    "fws student", "fws -", "federal work study",
    "work study",
    "ops student", "ops research assistant", "ops lab",
    "ops event", "ops administrative", "ops office",
    "ops documentation", "ops data", "ops it",
    "ops web", "ops digital", "ops content", "ops communications",
    "ops technology", "ops software", "ops computing",
    "ops instructional", "ops academic",
    "part-time internship", "student internship",
    "graduate assistant",
]

# Also allow any OPS/temp job whose title contains these tech/admin terms
OPS_PLUS_RELEVANT = [
    "web developer", "web development",
    "software", "data analyst", "data science",
    "it support", "it assistant", "tech support",
    "help desk", "information technology",
    "digital content", "graphic design",
    "social media", "communications coordinator",
    "research computing", "cybersecurity",
    "library assistant", "academic assistant",
    "accounting assistant", "finance assistant",
    "hr assistant", "human resources assistant",
    "peer mentor", "peer tutor", "tutoring",
    "content creator", "multimedia",
    "administrative assistant",
]

# Exclude full-time faculty / doctoral / professional roles
EXCLUDE_KEYWORDS = [
    "professor", "faculty", "post-doctoral", "postdoctoral",
    "physician", "physician ", "medical director", "dean",
    "associate professor", "assistant professor",
    "clinical assistant", "clinical associate",
    "veterinary technician", "dental assistant",
    "surgeon", "anesthesiology", "nursing",
    "staff veterinarian", "veterinary nursing",
]

# Role relevance for Lokesh (CS/tech/admin roles preferred)
PREFERRED_KEYWORDS = [
    "software", "web", "developer", "it ", "information technology",
    "data", "research", "computing", "computer", "technology",
    "engineering", "digital", "media", "content", "design",
    "library", "administrative", "office", "assistant",
    "accounting", "finance", "hr", "human resources",
    "communications", "marketing", "social media",
    "tutoring", "teaching", "peer", "mentor",
    "lab", "laboratory", "science",
]

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
    handlers=[
        logging.FileHandler(LOG_FILE),
        logging.StreamHandler(),
    ],
)
log = logging.getLogger(__name__)

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
                  "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,*/*;q=0.9",
    "Accept-Language": "en-US,en;q=0.9",
}

# ── Persistence ───────────────────────────────────────────────────────────────

def load_seen() -> set:
    if SEEN_FILE.exists():
        return set(json.loads(SEEN_FILE.read_text()).get("seen", []))
    return set()

def save_seen(seen: set):
    SEEN_FILE.write_text(json.dumps({"seen": list(seen), "updated": datetime.now().isoformat()}, indent=2))

def load_applied_ids() -> set:
    if APPLIED_FILE.exists():
        data = json.loads(APPLIED_FILE.read_text())
        return {str(entry["id"]) for entry in data.get("applied", [])}
    return set()

def job_hash(job_id: str) -> str:
    return hashlib.md5(f"uf-{job_id}".encode()).hexdigest()

# ── Scraper ───────────────────────────────────────────────────────────────────

def fetch_html(url: str) -> str:
    try:
        req = Request(url, headers=HEADERS)
        with urlopen(req, timeout=15) as r:
            return r.read().decode("utf-8", errors="ignore")
    except Exception as e:
        log.warning(f"fetch failed {url}: {e}")
        return ""

def parse_jobs_from_page(html: str) -> list[dict]:
    """Extract all job listings from a PageUp listing page."""
    jobs = []

    # Extract job links with IDs and slugs
    link_matches = list(re.finditer(
        r'href="/674/cw/en-us/job/(\d+)/([^"]+)">([^<]+)</a>', html
    ))
    dept_matches  = list(re.finditer(r'<span class="job-department">([^<]+)</span>', html))
    loc_matches   = list(re.finditer(r'<span class="location">([^<]+)</span>', html))
    date_matches  = list(re.finditer(r'<time datetime="[^"]+">([^<]+)</time>', html))
    summ_matches  = list(re.finditer(
        r'<tr class="summary">\s*<td[^>]*>(.*?)</td>', html, re.DOTALL
    ))

    for i, m in enumerate(link_matches):
        job_id, slug, title = m.group(1), m.group(2), m.group(3).strip()
        pos = m.start()

        # Find nearest dept/loc/date/summary after this link position
        dept = next((x.group(1).strip() for x in dept_matches if x.start() > pos), "")
        loc  = next((x.group(1).strip() for x in loc_matches  if x.start() > pos), "")
        date = next((x.group(1).strip() for x in date_matches if x.start() > pos), "")
        summ_raw = next((x.group(1) for x in summ_matches if x.start() > pos), "")
        summ = re.sub(r'\s+', ' ', re.sub(r'<[^>]+>', '', summ_raw)).strip()[:400]

        # Clean dept: strip numeric prefix
        dept_clean = re.sub(r'^\d+\s*-\s*', '', dept).strip()

        apply_url = JOB_LINK.format(id=job_id, slug=slug)

        jobs.append({
            "id": job_id,
            "title": title,
            "department": dept_clean,
            "location": loc,
            "closes": date,
            "summary": summ,
            "url": apply_url,
            "slug": slug,
        })

    return jobs

def scrape_all_uf_jobs(seen: set, max_pages: int = 5) -> list[dict]:
    """
    Scrape UF job listing pages.
    On first run (seen is empty) scans up to max_pages=15 to seed the dedup store.
    On subsequent runs scans only max_pages=5 — new jobs always appear at the top.
    Stops early if a full page of jobs are all already-seen (no new content).
    """
    if not seen:
        max_pages = 15  # first-run full scan

    all_jobs = []
    page = 1
    while page <= max_pages:
        url = f"{BASE_URL}/listing/?page={page}&page-items=20"
        log.info(f"Fetching UF jobs page {page}/{max_pages}...")
        html = fetch_html(url)
        if not html:
            break
        jobs = parse_jobs_from_page(html)
        if not jobs:
            break
        log.info(f"  → {len(jobs)} jobs on page {page}")
        all_jobs.extend(jobs)

        # Early stop: if every job on this page is already seen, no new content ahead
        page_ids = {job_hash(j["id"]) for j in jobs}
        if seen and page_ids.issubset(seen):
            log.info(f"  All jobs on page {page} already seen — stopping early")
            break

        if f"page={page+1}" not in html:
            break
        page += 1
        time.sleep(0.8)

    log.info(f"Total UF jobs scraped: {len(all_jobs)}")
    return all_jobs

# ── Filtering ─────────────────────────────────────────────────────────────────

def is_target_job(job: dict) -> bool:
    """Return True if this is a student/OPS/part-time/temp position for Lokesh."""
    title_lower = job["title"].lower()
    combined = (job["title"] + " " + job["summary"]).lower()

    # Hard exclude: full-time academic / medical / professional roles
    if any(kw in title_lower for kw in EXCLUDE_KEYWORDS):
        return False

    # Match: explicit student/OPS/FWS/work-study job types
    if any(kw in title_lower for kw in TARGET_KEYWORDS):
        return True

    # Match: OPS prefix + any relevant tech/admin term in title
    if title_lower.startswith("ops ") or "ops " in title_lower[:8]:
        if any(kw in combined for kw in OPS_PLUS_RELEVANT):
            return True

    # Match: relevant tech/admin title that's clearly a student/part-time role
    # (has "intern", "assistant", "aide", "part-time" in title but not professor)
    if any(kw in title_lower for kw in ["intern", "internship"]):
        return True
    if "student" in title_lower:
        return True

    return False

def relevance_score(job: dict) -> int:
    """Score how relevant this UF job is for a CS student."""
    combined = (job["title"] + " " + job["department"] + " " + job["summary"]).lower()
    return sum(1 for kw in PREFERRED_KEYWORDS if kw in combined)

# ── Resume generation (reuses resume_gen logic) ───────────────────────────────

from resume_gen import (
    build_tailored_resume, render_html, extract_jd_keywords, safe_filename
)

def generate_uf_resume(job: dict) -> Path | None:
    date_str = datetime.now().strftime("%Y-%m-%d")
    out_dir = RESUMES_DIR / date_str
    out_dir.mkdir(parents=True, exist_ok=True)

    fname = safe_filename(job["title"], job["department"][:30]) + ".html"
    out_path = out_dir / fname

    if out_path.exists():
        return out_path

    log.info(f"  Resume → {job['title']} [{job['id']}]")
    jd_text = job["summary"]  # Use scraped summary as JD
    tailored = build_tailored_resume(
        {"company": "University of Florida", "title": job["title"]},
        jd_text
    )
    html = render_html(tailored)
    out_path.write_text(html, encoding="utf-8")
    return out_path

# ── Email ─────────────────────────────────────────────────────────────────────

def build_uf_email(new_jobs: list[dict], resume_count: int, check_date: str) -> str:
    if not new_jobs:
        body = "<p>No new UF student/OPS/part-time job postings found today.</p>"
    else:
        # Sort by relevance score descending
        sorted_jobs = sorted(new_jobs, key=relevance_score, reverse=True)
        rows = ""
        for job in sorted_jobs:
            score = relevance_score(job)
            badge = ""
            if score >= 3:
                badge = ' <span style="background:#d4edda;color:#155724;padding:1px 6px;border-radius:3px;font-size:11px">⭐ Relevant</span>'
            rows += f"""<tr style="border-bottom:1px solid #f0f0f0">
  <td style="padding:9px 12px">
    <a href="{job['url']}" style="color:#0064B4;text-decoration:none;font-weight:600">{job['title']}</a>{badge}
    <div style="color:#666;font-size:12px;margin-top:2px">{job['department']}</div>
  </td>
  <td style="padding:9px 12px;color:#555;font-size:13px">{job['location']}</td>
  <td style="padding:9px 12px;color:#888;font-size:12px">Closes {job['closes']}</td>
  <td style="padding:9px 12px">
    <a href="{job['url']}" style="background:#0064B4;color:#fff;padding:4px 10px;border-radius:4px;text-decoration:none;font-size:12px">Apply</a>
  </td>
</tr>"""

        body = f"""
<p style="color:#333">Found <strong>{len(new_jobs)} new</strong> UF student/OPS/part-time posting(s) — apply fast, these fill quickly:</p>
<table style="width:100%;border-collapse:collapse;font-size:14px">
  <thead>
    <tr style="background:#f0f5ff;color:#555;text-align:left">
      <th style="padding:9px 12px;border-bottom:2px solid #dee2e6">Position</th>
      <th style="padding:9px 12px;border-bottom:2px solid #dee2e6">Location</th>
      <th style="padding:9px 12px;border-bottom:2px solid #dee2e6">Deadline</th>
      <th style="padding:9px 12px;border-bottom:2px solid #dee2e6"></th>
    </tr>
  </thead>
  <tbody>{rows}</tbody>
</table>"""

    resume_note = ""
    if resume_count > 0:
        resume_note = f"""
<div style="background:#f0f5ff;border:1px solid #c8d8ff;border-radius:6px;padding:12px 16px;margin-top:14px">
  <strong style="color:#0064B4">📄 {resume_count} tailored resume(s) saved</strong>
  <p style="margin:4px 0 0;font-size:13px;color:#555">
    Location: <code>/Users/lokesharora/personal_work/uf_jobs/resumes/{check_date}/</code><br>
    Open any .html in browser → Print → Save as PDF
  </p>
</div>"""

    return f"""<html><body style="font-family:Arial,sans-serif;max-width:860px;margin:0 auto;padding:20px;color:#333">
<div style="border-left:4px solid #0064B4;padding-left:16px;margin-bottom:18px">
  <h2 style="margin:0;color:#0064B4">UF Jobs Update — {check_date}</h2>
  <p style="margin:4px 0 0;color:#666;font-size:13px">
    explore.jobs.ufl.edu · Student Assistant · OPS · Part-Time · FWS · Temp
  </p>
</div>
{body}
{resume_note}
<hr style="border:none;border-top:1px solid #eee;margin:24px 0">
<p style="color:#aaa;font-size:11px">
  Already-applied jobs are never re-shown ·
  <a href="https://explore.jobs.ufl.edu/cw/en-us/listing/" style="color:#aaa">Browse all UF jobs</a> ·
  Add new applied IDs to uf_applied_jobs.json
</p>
</body></html>"""

def send_email(subject: str, html: str):
    if not GMAIL_APP_PASSWORD:
        log.error("GMAIL_APP_PASSWORD not set — email not sent")
        return False
    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"]    = GMAIL_USER
    msg["To"]      = RECIPIENT_EMAIL
    msg.attach(MIMEText(html, "html"))
    try:
        with smtplib.SMTP_SSL("smtp.gmail.com", 465) as s:
            s.login(GMAIL_USER, GMAIL_APP_PASSWORD)
            s.sendmail(GMAIL_USER, RECIPIENT_EMAIL, msg.as_string())
        log.info(f"Email sent → {RECIPIENT_EMAIL}")
        return True
    except Exception as e:
        log.error(f"Email failed: {e}")
        return False

# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    log.info("=" * 60)
    log.info(f"UF Jobs Tracker — {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    log.info("=" * 60)

    seen       = load_seen()
    applied_ids = load_applied_ids()
    log.info(f"Seen previously: {len(seen)} | Already applied: {len(applied_ids)}")

    all_jobs = scrape_all_uf_jobs(seen)

    # Filter to target job types
    target = [j for j in all_jobs if is_target_job(j)]
    log.info(f"Student/OPS/part-time jobs: {len(target)}/{len(all_jobs)}")

    # Remove already-applied and already-seen
    new_jobs = []
    new_hashes = set()
    for job in target:
        if job["id"] in applied_ids:
            continue
        h = job_hash(job["id"])
        if h not in seen:
            new_jobs.append(job)
            new_hashes.add(h)

    log.info(f"New (not applied, not seen): {len(new_jobs)}")

    # Update seen
    seen.update(new_hashes)
    save_seen(seen)

    # Generate resumes
    resume_paths = []
    if new_jobs:
        log.info("Generating tailored resumes...")
        RESUMES_DIR.mkdir(parents=True, exist_ok=True)
        for job in new_jobs:
            try:
                p = generate_uf_resume(job)
                if p:
                    resume_paths.append(p)
            except Exception as e:
                log.error(f"Resume failed for [{job['id']}]: {e}")

    # Send email
    check_date = datetime.now().strftime("%B %d, %Y")
    if new_jobs:
        subject = f"[UF Jobs] {len(new_jobs)} new posting(s) — {check_date}"
    else:
        subject = f"[UF Jobs] No new postings today — {check_date}"

    html = build_uf_email(new_jobs, len(resume_paths), datetime.now().strftime("%Y-%m-%d"))
    send_email(subject, html)

    log.info("Done.")
    return len(new_jobs)

if __name__ == "__main__":
    main()
