# Intern Tracker — Agent Context

This file gives any AI agent or new developer full context to understand,
maintain, or extend this project without needing prior conversation history.

---

## What this project does

Daily automated tracker that:
1. Scrapes 164+ US companies' career pages + 4 community GitHub repos for **Summer 2027** tech internship postings
2. Deduplicates against previously seen jobs
3. **Generates a tailored resume** (HTML) for every new posting found
4. Sends a **daily email digest** at 8 AM with new postings + resume locations

Target roles: SWE Intern, ML Intern, AI Intern, Data Science/Engineering Intern, Research Intern

---

## Owner profile

**Name:** Lokesh Arora  
**Email (UF):** lokesh.l@ufl.edu  
**LinkedIn:** linkedin.com/in/la03  
**Phone:** +91 8708728498  
**Status:** Incoming M.S. Computer Science, University of Florida, Fall 2026  
**Background:** 5+ years SWE experience at Nium (fintech, AI tooling) and Amazon  

**Resume highlights:**
- Nium (Senior SWE, Apr 2025–Present): AI chatbot, knowledge dashboard, 5M+ tx/month wallet platform
- Nium (SDE II, Feb 2023–Mar 2025): workflow automation, DLQ retry, FPX payment integration
- Amazon (SDE I, Feb 2022–Feb 2023): Node.js/TypeScript for Amazon Fresh, DB optimization
- ZS Associates (Technical Associate, Jan 2021–Feb 2022): Python microservices, REST APIs, healthcare data

**Key skills:** Java, Python, TypeScript, Node.js, LangChain, RAG, LLMs, AWS, Docker, Kubernetes, React/Next.js

**Projects:**
- AI Document Chat Assistant: RAG + LangChain + Sentence-BERT + Vector Search
- FinTrack Dashboard: Next.js + PostgreSQL + Prisma

**Daily email recipient:** 3lokesharora@gmail.com

---

## File structure

```
intern-tracker/
├── tracker.py          # Main script: scrapes jobs, generates resumes, sends email
├── resume_gen.py       # Resume tailoring: keyword matching, HTML generation
├── companies.json      # 164 companies with career URLs and platform types
├── setup.sh            # One-time setup: Gmail creds, scheduling (Mac + Linux)
├── CLAUDE.md           # This file — full context for agents/developers
├── .gitignore          # Excludes: .env, seen_jobs.json, tracker.log, resumes/
│
├── .env                # NOT in git — Gmail credentials (see Setup below)
├── seen_jobs.json      # NOT in git — dedup store, auto-generated on first run
├── tracker.log         # NOT in git — run logs, auto-generated
└── resumes/            # NOT in git — generated per-job HTML resumes
    └── YYYY-MM-DD/
        └── CompanyName_Role_Title.html
```

---

## How tracker.py works

### Phase 1 — GitHub community trackers (primary source)
Fetches raw README.md from 4 repos that are updated daily:
- `speedyapply/2027-SWE-College-Jobs` — 272+ internships, updated daily
- `speedyapply/2027-AI-College-Jobs` — AI/ML specific
- `vanshb03/Summer2027-Internships` — community-maintained
- `zapplyjobs/Internships-2027` — broad 2027 tech list

Parses markdown tables, filters by role keywords, extracts apply links.

### Phase 2 — Direct company API checks
For each company in `companies.json`:
- **Greenhouse** platform: hits `boards-api.greenhouse.io/v1/boards/{id}/jobs`
- **Lever** platform: hits `api.lever.co/v0/postings/{id}`
- **Custom/other**: fetches HTML from career URL, extracts anchor links matching intern keywords

### Phase 3 — Resume generation (resume_gen.py)
For each new job:
1. Fetches job description HTML from the posting URL
2. Extracts keywords using regex tokenization
3. Scores every resume bullet against JD keywords
4. Reorders bullets, projects, skills by descending relevance score
5. Detects role type (SWE / ML / Data / AI) → picks matching summary template
6. Renders HTML resume with the same visual style as the original LaTeX PDF
7. Saves to `resumes/YYYY-MM-DD/Company_Role.html`

To convert to PDF: open HTML in browser → File → Print → Save as PDF (or Cmd+P on Mac).

### Deduplication
- Each job is identified by `md5(company + title + url)`
- `seen_jobs.json` stores all previously seen IDs
- Only truly new jobs generate resumes and appear in the email

### Email
- Gmail SMTP via port 465 (SSL)
- HTML email with job table + note about resume locations
- Credentials from `.env` file

---

## Setup on a new machine

### Requirements
- Python 3.8+ (pre-installed on Mac; `sudo apt install python3` on Ubuntu)
- Git
- Internet access
- A Gmail account with 2-Step Verification enabled

### Steps

```bash
# 1. Clone the repo
git clone https://github.com/lokesharora2000/intern-tracker
cd intern-tracker

# 2. Run setup (handles credentials + scheduling automatically)
bash setup.sh
```

`setup.sh` will:
- Prompt for Gmail App Password (one-time)
- Send a test email to confirm credentials work
- Install the daily 8 AM schedule (launchd on Mac, cron on Linux)
- Optionally run immediately

### Gmail App Password (required, one-time per Google account)
1. Go to https://myaccount.google.com/apppasswords
2. Security → 2-Step Verification must be ON
3. App passwords → Create → Name: "Intern Tracker"
4. Copy the 16-character password shown (format: `xxxx xxxx xxxx xxxx`)

The password is stored in `.env` (chmod 600, never committed to git).

### What the .env file looks like
```
GMAIL_USER=3lokesharora@gmail.com
GMAIL_APP_PASSWORD=xxxx xxxx xxxx xxxx
RECIPIENT_EMAIL=3lokesharora@gmail.com
```

---

## Running manually

```bash
cd ~/path/to/intern-tracker
set -a && source .env && set +a
python3 tracker.py
```

Or if you want to reset and re-find all jobs (e.g. on a new machine):
```bash
rm -f seen_jobs.json   # clears dedup store — all current jobs treated as "new"
python3 tracker.py
```

---

## Scheduling

### macOS (launchd) — set up by setup.sh
```bash
# Check status
launchctl list | grep interntracker

# Stop
launchctl unload ~/Library/LaunchAgents/com.lokesh.interntracker.plist

# Start
launchctl load ~/Library/LaunchAgents/com.lokesh.interntracker.plist
```

**Important:** The Mac must be awake at 8 AM for launchd to trigger. If the Mac is asleep, the job runs when it wakes up (launchd catches missed jobs within the same day).

### Linux (cron) — set up by setup.sh
```bash
crontab -l          # view schedule
crontab -e          # edit schedule
```

The cron entry looks like:
```
0 8 * * * cd /path/to/intern-tracker && set -a && source .env && set +a && python3 tracker.py >> tracker.log 2>&1
```

---

## Adding or removing companies

Edit `companies.json`. Each entry needs:
```json
{
  "name": "Company Name",
  "career_url": "https://careers.example.com/jobs",
  "platform": "greenhouse",        // greenhouse | lever | workday | ashby | custom
  "greenhouse_id": "companyslug",  // only for greenhouse platform
  "tier": "AI Lab",
  "tags": ["SWE", "ML", "Data"]
}
```

For Greenhouse companies, find the board ID by visiting `https://boards.greenhouse.io/COMPANY` — the slug in the URL is the `greenhouse_id`.

---

## Resume generation details

Resumes are saved as `resumes/YYYY-MM-DD/CompanyName_RoleTitle.html`.

The tailoring logic in `resume_gen.py`:
- **Role detection**: if JD has "machine learning", "pytorch", "model training" → ML template; "data science", "etl", "pipeline" → Data template; "llm", "rag", "generative" → AI template; else → SWE template
- **Bullet scoring**: each bullet gets a score = count of JD keywords it contains; higher score → listed first
- **Skills reordering**: skill categories sorted by number of JD keywords matched
- **No fabrication**: only reorders and reframes existing facts — never invents skills or experience

To improve resume quality further, you can optionally add an Anthropic API key to `.env`:
```
ANTHROPIC_API_KEY=sk-ant-...
```
When present, `resume_gen.py` will use Claude to write the tailored content instead of keyword matching (better quality, ~$0.003/resume using claude-haiku).

---

## GitHub repo

https://github.com/lokesharora2000/intern-tracker

What IS committed: `tracker.py`, `resume_gen.py`, `companies.json`, `setup.sh`, `CLAUDE.md`  
What is NOT committed: `.env`, `seen_jobs.json`, `tracker.log`, `resumes/`
