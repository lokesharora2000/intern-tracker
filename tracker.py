#!/usr/bin/env python3
"""
Summer 2027 Internship Tracker
Daily job monitor for SWE/ML/AI/Data internships
Sends email digest with new postings
"""

import json
import os
import re
import smtplib
import hashlib
import time
import random
import logging
from datetime import datetime
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from pathlib import Path
from urllib.request import urlopen, Request
from urllib.error import URLError, HTTPError
from urllib.parse import urlencode, quote_plus

# ── Config ──────────────────────────────────────────────────────────────────

SCRIPT_DIR = Path(__file__).parent
SEEN_JOBS_FILE = SCRIPT_DIR / "seen_jobs.json"
LOG_FILE = SCRIPT_DIR / "tracker.log"
COMPANIES_FILE = SCRIPT_DIR / "companies.json"

# Email — set via env vars or edit directly
GMAIL_USER = os.environ.get("GMAIL_USER", "3lokesharora@gmail.com")
GMAIL_APP_PASSWORD = os.environ.get("GMAIL_APP_PASSWORD", "")  # Gmail app password
RECIPIENT_EMAIL = os.environ.get("RECIPIENT_EMAIL", "3lokesharora@gmail.com")

TARGET_KEYWORDS = [
    "software engineer intern", "swe intern", "software engineering intern",
    "ml intern", "machine learning intern", "ai intern", "artificial intelligence intern",
    "data science intern", "data engineer intern", "data analyst intern",
    "research intern", "backend intern", "frontend intern", "platform intern",
    "applied scientist intern", "research scientist intern", "nlp intern",
    "computer vision intern", "deep learning intern", "llm intern",
]

TARGET_SEASON_KEYWORDS = ["2027", "summer 2027", "summer intern 2027"]

# Greenhouse API base
GREENHOUSE_API = "https://boards-api.greenhouse.io/v1/boards/{}/jobs?content=true"

# Lever API base
LEVER_API = "https://api.lever.co/v0/postings/{}"

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
    handlers=[
        logging.FileHandler(LOG_FILE),
        logging.StreamHandler()
    ]
)
log = logging.getLogger(__name__)

# ── Job ID / dedup ───────────────────────────────────────────────────────────

def load_seen_jobs() -> set:
    if SEEN_JOBS_FILE.exists():
        with open(SEEN_JOBS_FILE) as f:
            data = json.load(f)
        return set(data.get("seen", []))
    return set()

def save_seen_jobs(seen: set):
    with open(SEEN_JOBS_FILE, "w") as f:
        json.dump({"seen": list(seen), "last_updated": datetime.now().isoformat()}, f, indent=2)

def job_id(company: str, title: str, url: str) -> str:
    raw = f"{company}|{title}|{url}".lower()
    return hashlib.md5(raw.encode()).hexdigest()

# ── HTTP helpers ──────────────────────────────────────────────────────────────

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
                  "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept": "application/json, text/html, */*",
    "Accept-Language": "en-US,en;q=0.9",
}

def fetch_json(url: str, timeout: int = 15) -> dict | list | None:
    try:
        req = Request(url, headers=HEADERS)
        with urlopen(req, timeout=timeout) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except (URLError, HTTPError, json.JSONDecodeError, Exception) as e:
        log.warning(f"fetch_json failed for {url}: {e}")
        return None

def fetch_html(url: str, timeout: int = 15) -> str:
    try:
        req = Request(url, headers=HEADERS)
        with urlopen(req, timeout=timeout) as resp:
            return resp.read().decode("utf-8", errors="ignore")
    except Exception as e:
        log.warning(f"fetch_html failed for {url}: {e}")
        return ""

# ── Keyword matching ──────────────────────────────────────────────────────────

def is_relevant_title(title: str) -> bool:
    title_lower = title.lower()
    return any(kw in title_lower for kw in TARGET_KEYWORDS)

def is_relevant_season(title: str, description: str = "") -> bool:
    combined = (title + " " + description).lower()
    # If no year mentioned, assume it might be relevant (catch-all)
    has_year = any(yr in combined for yr in ["2025", "2026", "2027", "2028"])
    if not has_year:
        return True
    return any(kw in combined for kw in TARGET_SEASON_KEYWORDS)

# ── Platform scrapers ─────────────────────────────────────────────────────────

def scrape_greenhouse(company: dict) -> list[dict]:
    greenhouse_id = company.get("greenhouse_id") or company["name"].lower().replace(" ", "")
    url = GREENHOUSE_API.format(greenhouse_id)
    data = fetch_json(url)
    if not data or "jobs" not in data:
        return []

    results = []
    for job in data["jobs"]:
        title = job.get("title", "")
        if not is_relevant_title(title):
            continue
        desc = job.get("content", "")
        if not is_relevant_season(title, desc):
            continue
        job_url = job.get("absolute_url", "")
        results.append({
            "company": company["name"],
            "title": title,
            "url": job_url,
            "location": ", ".join(
                [loc.get("name", "") for loc in job.get("offices", [])]
            ) or "US",
            "platform": "Greenhouse",
            "tags": company.get("tags", []),
        })
    return results


def scrape_lever(company: dict) -> list[dict]:
    lever_id = company.get("lever_id") or company["name"].lower().replace(" ", "").replace("/", "")
    # Parse lever_id from career_url if available
    career_url = company.get("career_url", "")
    if "lever.co/" in career_url:
        parts = career_url.split("lever.co/")
        if len(parts) > 1:
            lever_id = parts[1].split("?")[0].strip("/")

    url = LEVER_API.format(lever_id)
    data = fetch_json(url)
    if not data or not isinstance(data, list):
        return []

    results = []
    for job in data:
        title = job.get("text", "")
        categories = job.get("categories", {})
        commitment = categories.get("commitment", "")
        if "intern" not in commitment.lower() and not is_relevant_title(title):
            continue
        if not is_relevant_title(title):
            continue
        job_url = job.get("hostedUrl", "")
        location = categories.get("location", "US")
        results.append({
            "company": company["name"],
            "title": title,
            "url": job_url,
            "location": location,
            "platform": "Lever",
            "tags": company.get("tags", []),
        })
    return results


def parse_github_intern_table(raw_md: str, source_label: str) -> list[dict]:
    """Parse a markdown internship table from GitHub community tracker repos."""
    results = []
    for line in raw_md.split("\n"):
        if "|" not in line:
            continue
        cols = [c.strip() for c in line.split("|") if c.strip()]
        if len(cols) < 3:
            continue
        # Skip header/separator lines
        if all(set(c) <= set("-: ") for c in cols if c):
            continue

        col0, col1 = cols[0], cols[1] if len(cols) > 1 else ""
        col2 = cols[2] if len(cols) > 2 else ""
        col3 = cols[3] if len(cols) > 3 else ""

        # Company name from first column (may be a markdown link or plain text)
        company_match = re.search(r'\[([^\]]+)\]\(([^)]+)\)', col0)
        company_name = company_match.group(1) if company_match else col0.strip()
        if not company_name or company_name.startswith("-"):
            continue

        # Role from second column
        role_col = re.sub(r'\[([^\]]+)\]\([^)]+\)', r'\1', col1).strip()
        if not role_col or role_col.startswith("-"):
            continue
        if not is_relevant_title(role_col):
            continue

        location_col = re.sub(r'\[([^\]]+)\]\([^)]+\)', r'\1', col2).strip()

        # Apply link: look in col3, col4, or fall back to col0 link
        apply_url = ""
        for col in cols[3:]:
            m = re.search(r'\[.*?\]\(([^)]+)\)', col)
            if m:
                apply_url = m.group(1)
                break
        if not apply_url and company_match:
            apply_url = company_match.group(2)
        if not apply_url:
            continue

        # Skip closed/filled markers
        if any(marker in col3.lower() for marker in ["closed", "🔒", "filled"]):
            continue

        results.append({
            "company": company_name,
            "title": role_col,
            "url": apply_url,
            "location": location_col or "US",
            "platform": source_label,
            "tags": [],
        })
    return results


def scrape_github_trackers() -> list[dict]:
    """Scrape community-maintained GitHub repos that track 2027 internships daily."""
    trackers = [
        {
            "label": "speedyapply/2027-SWE",
            "url": "https://raw.githubusercontent.com/speedyapply/2027-SWE-College-Jobs/main/README.md",
        },
        {
            "label": "speedyapply/2027-AI",
            "url": "https://raw.githubusercontent.com/speedyapply/2027-AI-College-Jobs/main/README.md",
        },
        {
            "label": "vanshb03/Summer2027",
            "url": "https://raw.githubusercontent.com/vanshb03/Summer2027-Internships/dev/README.md",
        },
        {
            "label": "zapplyjobs/2027",
            "url": "https://raw.githubusercontent.com/zapplyjobs/Internships-2027/main/README.md",
        },
    ]

    all_results = []
    for tracker in trackers:
        log.info(f"Checking GitHub tracker: {tracker['label']}...")
        raw = fetch_html(tracker["url"])
        if not raw:
            continue
        found = parse_github_intern_table(raw, tracker["label"])
        log.info(f"  → {len(found)} relevant postings")
        all_results.extend(found)
        time.sleep(0.5)

    return all_results


def scrape_company_generic(company: dict) -> list[dict]:
    """Generic scraper: fetch career page and look for intern job links."""
    url = company.get("career_url", "")
    if not url:
        return []
    html = fetch_html(url)
    if not html:
        return []

    results = []
    # Look for job title patterns near intern keywords
    # Find all anchor tags
    anchors = re.findall(r'<a[^>]+href=["\']([^"\']+)["\'][^>]*>([^<]{5,120})</a>', html, re.IGNORECASE)
    for href, text in anchors:
        text_clean = re.sub(r'\s+', ' ', text).strip()
        if not is_relevant_title(text_clean):
            continue
        if not is_relevant_season(text_clean):
            continue
        # Make absolute URL
        if href.startswith("http"):
            full_url = href
        elif href.startswith("/"):
            from urllib.parse import urlparse
            parsed = urlparse(url)
            full_url = f"{parsed.scheme}://{parsed.netloc}{href}"
        else:
            continue
        results.append({
            "company": company["name"],
            "title": text_clean,
            "url": full_url,
            "location": "US",
            "platform": "Career Page",
            "tags": company.get("tags", []),
        })
    return results


# ── Main scrape loop ──────────────────────────────────────────────────────────

def scrape_all() -> list[dict]:
    with open(COMPANIES_FILE) as f:
        config = json.load(f)

    companies = config["companies"]
    all_jobs = []

    # Primary source: community GitHub trackers (updated daily, most comprehensive)
    log.info("=" * 40)
    log.info("Phase 1: GitHub community trackers")
    log.info("=" * 40)
    github_jobs = scrape_github_trackers()
    log.info(f"Total from GitHub trackers: {len(github_jobs)}")
    all_jobs.extend(github_jobs)

    # Secondary: Greenhouse/Lever APIs for companies not well-covered by trackers
    log.info("=" * 40)
    log.info("Phase 2: Direct company API checks")
    log.info("=" * 40)
    for company in companies:
        name = company["name"]
        platform = company.get("platform", "custom")
        log.info(f"Checking {name} ({platform})...")

        try:
            if platform == "greenhouse" and company.get("greenhouse_id"):
                jobs = scrape_greenhouse(company)
            elif platform == "lever":
                jobs = scrape_lever(company)
            else:
                jobs = scrape_company_generic(company)

            log.info(f"  → {len(jobs)} relevant postings")
            all_jobs.extend(jobs)
        except Exception as e:
            log.error(f"  → Error scraping {name}: {e}")

        # Polite delay between requests
        time.sleep(random.uniform(0.5, 1.5))

    return all_jobs


# ── Email ─────────────────────────────────────────────────────────────────────

def build_email_html(new_jobs: list[dict], check_date: str) -> str:
    if not new_jobs:
        body = "<p>No new Summer 2027 internship postings found today. Check back tomorrow!</p>"
    else:
        # Group by company
        by_company: dict[str, list] = {}
        for job in new_jobs:
            by_company.setdefault(job["company"], []).append(job)

        rows = ""
        for company, jobs in sorted(by_company.items()):
            for job in jobs:
                tags = " ".join(f'<span style="background:#e8f4fd;color:#1a73e8;padding:2px 6px;border-radius:3px;font-size:11px;margin-right:3px">{t}</span>' for t in job.get("tags", []))
                rows += f"""
                <tr style="border-bottom:1px solid #f0f0f0">
                  <td style="padding:10px 12px;font-weight:600;color:#333">{company}</td>
                  <td style="padding:10px 12px">
                    <a href="{job['url']}" style="color:#1a73e8;text-decoration:none;font-weight:500">{job['title']}</a>
                    <div style="margin-top:4px">{tags}</div>
                  </td>
                  <td style="padding:10px 12px;color:#666;font-size:13px">{job.get('location','US')}</td>
                  <td style="padding:10px 12px;color:#888;font-size:12px">{job.get('platform','')}</td>
                </tr>"""

        body = f"""
        <p style="color:#333;font-size:15px">Found <strong>{len(new_jobs)} new</strong> Summer 2027 internship posting(s) today:</p>
        <table style="width:100%;border-collapse:collapse;font-family:Arial,sans-serif;font-size:14px">
          <thead>
            <tr style="background:#f8f9fa;color:#555;text-align:left">
              <th style="padding:10px 12px;border-bottom:2px solid #dee2e6">Company</th>
              <th style="padding:10px 12px;border-bottom:2px solid #dee2e6">Role</th>
              <th style="padding:10px 12px;border-bottom:2px solid #dee2e6">Location</th>
              <th style="padding:10px 12px;border-bottom:2px solid #dee2e6">Source</th>
            </tr>
          </thead>
          <tbody>{rows}</tbody>
        </table>
        <p style="margin-top:20px;color:#888;font-size:12px">
          Also check:
          <a href="https://github.com/SimplifyJobs/Summer2027-Internships">SimplifyJobs GitHub</a> ·
          <a href="https://www.levels.fyi/internships/">Levels.fyi Intern Tracker</a> ·
          <a href="https://joinhandshake.com/search?query=software+engineer+intern+2027">Handshake</a>
        </p>"""

    return f"""
    <html><body style="font-family:Arial,sans-serif;max-width:900px;margin:0 auto;padding:20px;color:#333">
      <div style="border-left:4px solid #1a73e8;padding-left:16px;margin-bottom:20px">
        <h2 style="margin:0;color:#1a73e8">Summer 2027 Internship Update</h2>
        <p style="margin:4px 0 0;color:#666;font-size:13px">{check_date} · SWE · ML · AI · Data roles · US companies</p>
      </div>
      {body}
      <hr style="border:none;border-top:1px solid #eee;margin:30px 0">
      <p style="color:#aaa;font-size:11px">
        Tracking {len(open(COMPANIES_FILE).read().split('"name"')) - 1} companies ·
        intern-tracker running on your Mac ·
        Edit ~/personal_work/intern-tracker/companies.json to add/remove companies
      </p>
    </body></html>"""


def send_email(subject: str, html_body: str):
    if not GMAIL_APP_PASSWORD:
        log.error("GMAIL_APP_PASSWORD not set. Email not sent. See README for setup.")
        return False

    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"] = GMAIL_USER
    msg["To"] = RECIPIENT_EMAIL
    msg.attach(MIMEText(html_body, "html"))

    try:
        with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
            server.login(GMAIL_USER, GMAIL_APP_PASSWORD)
            server.sendmail(GMAIL_USER, RECIPIENT_EMAIL, msg.as_string())
        log.info(f"Email sent to {RECIPIENT_EMAIL}")
        return True
    except Exception as e:
        log.error(f"Failed to send email: {e}")
        return False


# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    log.info("=" * 60)
    log.info(f"Summer 2027 Internship Tracker — {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    log.info("=" * 60)

    seen = load_seen_jobs()
    log.info(f"Loaded {len(seen)} previously seen jobs")

    all_jobs = scrape_all()
    log.info(f"Total relevant jobs found: {len(all_jobs)}")

    # Filter to new jobs only
    new_jobs = []
    new_ids = set()
    for job in all_jobs:
        jid = job_id(job["company"], job["title"], job["url"])
        if jid not in seen:
            new_jobs.append(job)
            new_ids.add(jid)

    log.info(f"New jobs (not seen before): {len(new_jobs)}")

    # Save updated seen set
    seen.update(new_ids)
    save_seen_jobs(seen)

    # Build and send email
    check_date = datetime.now().strftime("%B %d, %Y")
    if new_jobs:
        subject = f"[Intern Tracker] {len(new_jobs)} new Summer 2027 posting(s) — {check_date}"
    else:
        subject = f"[Intern Tracker] No new postings today — {check_date}"

    html = build_email_html(new_jobs, check_date)
    send_email(subject, html)

    log.info("Done.")
    return len(new_jobs)


if __name__ == "__main__":
    main()
