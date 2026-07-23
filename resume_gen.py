#!/usr/bin/env python3
"""
Resume generator — tailors Lokesh's base resume to a specific job description
using keyword matching and rule-based scoring. No external API needed.
Saves output as a clean HTML file (open in browser → Print → Save as PDF).
"""

import re
import logging
from pathlib import Path
from urllib.request import urlopen, Request
from datetime import datetime

log = logging.getLogger(__name__)

SCRIPT_DIR = Path(__file__).parent
RESUMES_DIR = SCRIPT_DIR / "resumes"

# ── Candidate data ────────────────────────────────────────────────────────────

CONTACT = {
    "name": "Lokesh Arora",
    "email": "lokesh.l@ufl.edu",
    "linkedin": "linkedin.com/in/la03",
    "phone": "+91 8708728498",
}

EDUCATION = [
    {
        "school": "University of Florida",
        "location": "Gainesville, FL",
        "degree": "M.S. in Computer Science",
        "dates": "Fall 2026 (Incoming)",
    },
    {
        "school": "Thapar Institute of Engineering and Technology",
        "location": "Patiala, Punjab",
        "degree": "B.E. in Computer Science & Engineering (GPA: 8.51)",
        "dates": "Aug 2017 – Aug 2021",
    },
]

EXPERIENCE = [
    {
        "company": "Nium",
        "location": "Bengaluru, India",
        "title": "Senior Software Engineer",
        "dates": "April 2025 – Present",
        "keywords": ["ai", "chatbot", "llm", "knowledge", "wallet", "fintech", "transactions",
                     "architecture", "platform", "productivity", "incident", "backend", "system design"],
        "bullets": [
            "Built an internal AI-powered chatbot and knowledge dashboard for architecture search, document retrieval, onboarding support, and incident knowledge discovery",
            "Improved engineering productivity by enabling faster troubleshooting, process documentation, and knowledge summarization using AI-assisted tooling",
            "Designed and led development of a unified wallet platform handling 5M+ transactions/month, improving reliability, latency, and operational support",
        ],
    },
    {
        "company": "Nium",
        "location": "Bengaluru, India",
        "title": "Software Development Engineer II",
        "dates": "Feb 2023 – Mar 2025",
        "keywords": ["automation", "workflow", "notification", "retry", "dlq", "backend",
                     "api", "fintech", "sla", "reliability", "integration", "payment"],
        "bullets": [
            "Built workflow automation solutions including Email Notification Services, onboarding reminders, and reusable operational templates, improving SLA by 20%",
            "Implemented DLQ-based retry workflows and failure recovery mechanisms, reducing manual intervention and improving operational efficiency",
            "Integrated FPX funding method and supported backend services through API maintenance, timeout handling, troubleshooting, and issue resolution",
        ],
    },
    {
        "company": "Amazon",
        "location": "Bangalore, India",
        "title": "Software Development Engineer I",
        "dates": "Feb 2022 – Feb 2023",
        "keywords": ["node.js", "typescript", "javascript", "web", "frontend", "database",
                     "sql", "performance", "optimization", "e-commerce", "large-scale", "on-call"],
        "bullets": [
            "Built real-time web services and UI-facing workflows for Amazon Fresh using Node.js and TypeScript, improving engagement by 10%",
            "Improved DB performance by 20% through query optimization, indexing, debugging, and production troubleshooting",
            "Supported large-scale systems through on-call issue resolution, technical documentation, peer mentoring, and operational debugging",
        ],
    },
    {
        "company": "ZS Associates",
        "location": "Gurgaon, India",
        "title": "Technical Associate",
        "dates": "Jan 2021 – Feb 2022",
        "keywords": ["python", "microservices", "rest", "api", "data", "analytics",
                     "healthcare", "docker", "kubernetes", "deployment"],
        "bullets": [
            "Developed Python-based microservices, REST APIs, and data workflows for healthcare reporting and internal analytics",
            "Supported deployment, debugging, maintenance, and backend troubleshooting using Docker and Kubernetes",
        ],
    },
]

PROJECTS = [
    {
        "name": "AI Document Chat Assistant",
        "tech": "LangChain, Sentence-BERT, OpenAI, Vector Search",
        "description": "Built a RAG-based assistant for document Q&A, semantic search, summarization, and knowledge discovery using embeddings and vector retrieval",
        "keywords": ["ai", "llm", "rag", "vector", "embedding", "langchain", "nlp",
                     "machine learning", "ml", "openai", "search", "bert", "transformer"],
    },
    {
        "name": "FinTrack — Personal Finance Dashboard",
        "tech": "Next.js, TypeScript, PostgreSQL, Prisma",
        "description": "Built a web-based dashboard for analytics, workflow tracking, and user-facing data visualization with strong frontend and backend integration",
        "keywords": ["next.js", "typescript", "postgresql", "database", "frontend",
                     "dashboard", "analytics", "fullstack", "web", "react"],
    },
]

SKILLS = [
    {"label": "Languages", "items": "Java, Python, C++, TypeScript, Node.js, JavaScript",
     "keywords": ["java", "python", "c++", "typescript", "node", "javascript"]},
    {"label": "AI/ML", "items": "LLMs, LangChain, RAG, Vector Search, GenAI Tools, Transformers",
     "keywords": ["ai", "ml", "machine learning", "llm", "rag", "vector", "langchain",
                  "deep learning", "nlp", "generative", "transformer", "bert"]},
    {"label": "Web & Frontend", "items": "React, Next.js, HTML, CSS, REST APIs, GraphQL",
     "keywords": ["react", "next.js", "html", "css", "frontend", "web", "graphql", "rest"]},
    {"label": "Cloud & Systems", "items": "AWS, Docker, Kubernetes, Linux, macOS, Windows",
     "keywords": ["aws", "cloud", "docker", "kubernetes", "linux", "devops", "infrastructure"]},
    {"label": "Databases", "items": "PostgreSQL, MySQL, Redis, MongoDB, DynamoDB",
     "keywords": ["sql", "database", "postgresql", "mysql", "redis", "mongodb", "nosql", "dynamo"]},
    {"label": "Data Science", "items": "Pandas, NumPy, Scikit-learn, Jupyter, Data Pipelines",
     "keywords": ["data science", "pandas", "numpy", "scikit", "jupyter", "data pipeline",
                  "analytics", "statistics", "data engineering"]},
    {"label": "Automation & Tools", "items": "Power Automate, Low-Code Workflows, Monitoring, Logging",
     "keywords": ["automation", "workflow", "monitoring", "logging", "observability"]},
]

SUMMARY_TEMPLATES = {
    "swe": "Software Engineer with 5+ years of experience building scalable backend systems and high-throughput platforms across fintech and enterprise environments. Strong proficiency in {top_skills}. Incoming M.S. Computer Science student at the University of Florida (Fall 2026).",
    "ml": "Software Engineer with hands-on experience building AI-powered systems, RAG pipelines, and LLM-based tooling across production fintech environments. Proficient in {top_skills}. Incoming M.S. Computer Science student at the University of Florida (Fall 2026).",
    "data": "Software Engineer and data practitioner with 5+ years building data workflows, analytics systems, and backend APIs across fintech and healthcare domains. Skilled in {top_skills}. Incoming M.S. Computer Science student at the University of Florida (Fall 2026).",
    "ai": "Software Engineer with deep experience building AI-powered productivity tools, chatbots, knowledge systems, and LLM integrations in production environments. Proficient in {top_skills}. Incoming M.S. Computer Science student at the University of Florida (Fall 2026).",
    "general": "Software Engineer with 5+ years of experience across backend systems, AI tooling, and workflow automation in fintech and enterprise environments. Skilled in {top_skills}. Incoming M.S. Computer Science student at the University of Florida (Fall 2026).",
}

# ── Keyword matching ──────────────────────────────────────────────────────────

def extract_jd_keywords(jd_text: str) -> set[str]:
    """Extract meaningful keywords from a job description."""
    text = jd_text.lower()
    # Remove common filler words
    stopwords = {"and", "or", "the", "a", "an", "in", "of", "to", "for", "is", "are",
                 "will", "you", "we", "our", "your", "with", "that", "this", "have",
                 "be", "as", "at", "by", "from", "on", "not", "what", "how", "can",
                 "team", "work", "role", "position", "job", "candidate", "experience",
                 "skills", "responsibilities", "requirements", "strong", "good", "ability"}
    tokens = re.findall(r'[a-z][a-z0-9\.\+\#\-]{1,}', text)
    return {t for t in tokens if t not in stopwords and len(t) > 2}


def score_text(text: str, jd_keywords: set[str]) -> int:
    """Score a text snippet by how many JD keywords it contains."""
    lower = text.lower()
    return sum(1 for kw in jd_keywords if kw in lower)


def detect_role_type(title: str, jd_keywords: set[str]) -> str:
    """Detect whether this is primarily SWE, ML, Data, or AI role."""
    combined = title.lower() + " " + " ".join(jd_keywords)
    if any(k in combined for k in ["machine learning", "ml", "deep learning", "neural", "model training", "pytorch", "tensorflow"]):
        return "ml"
    if any(k in combined for k in ["data science", "data scientist", "data engineer", "analytics", "etl", "pipeline"]):
        return "data"
    if any(k in combined for k in ["ai", "artificial intelligence", "llm", "rag", "generative", "nlp", "chatbot"]):
        return "ai"
    return "swe"


# ── Resume assembly ───────────────────────────────────────────────────────────

def build_tailored_resume(job: dict, jd_text: str) -> dict:
    """Return a tailored resume data dict based on JD keyword matching."""
    jd_keywords = extract_jd_keywords(jd_text) if jd_text else set()
    role_type = detect_role_type(job.get("title", ""), jd_keywords)

    # Score and reorder experience bullets per job
    tailored_exp = []
    for exp in EXPERIENCE:
        scored_bullets = sorted(
            exp["bullets"],
            key=lambda b: score_text(b, jd_keywords),
            reverse=True
        )
        tailored_exp.append({**exp, "bullets": scored_bullets})

    # Sort experience entries by relevance to JD
    tailored_exp.sort(
        key=lambda e: sum(score_text(b, jd_keywords) for b in e["bullets"]),
        reverse=True
    )

    # Score and reorder projects
    scored_projects = sorted(
        PROJECTS,
        key=lambda p: score_text(p["description"] + " " + p["tech"], jd_keywords),
        reverse=True
    )

    # Score and reorder skills sections
    scored_skills = sorted(
        SKILLS,
        key=lambda s: sum(1 for k in s["keywords"] if k in jd_keywords),
        reverse=True
    )

    # Pick top skills for summary
    top_matched_skills = []
    for skill in scored_skills[:3]:
        # Take first 2 items from each top skill category
        items = [s.strip() for s in skill["items"].split(",")][:2]
        top_matched_skills.extend(items)
    top_skills_str = ", ".join(top_matched_skills[:5]) if top_matched_skills else "Python, Java, TypeScript"

    summary = SUMMARY_TEMPLATES[role_type].format(top_skills=top_skills_str)

    return {
        "contact": CONTACT,
        "summary": summary,
        "experience": tailored_exp,
        "projects": scored_projects,
        "skills": scored_skills[:5],  # top 5 skill categories
        "education": EDUCATION,
        "job": job,
    }


# ── HTML rendering ────────────────────────────────────────────────────────────

def render_html(resume: dict) -> str:
    c = resume["contact"]
    job = resume["job"]

    exp_html = ""
    for exp in resume["experience"]:
        bullets = "\n".join(f"    <li>{b}</li>" for b in exp["bullets"])
        exp_html += f"""
  <div class="job-entry">
    <div class="job-header"><span class="job-company">{exp['company']}</span><span class="job-location">{exp['location']}</span></div>
    <div class="job-header"><span class="job-title">{exp['title']}</span><span class="job-dates">{exp['dates']}</span></div>
    <ul>
{bullets}
    </ul>
  </div>"""

    proj_html = ""
    for p in resume["projects"]:
        proj_html += f'  <p><span class="project-title">{p["name"]}</span>: <span class="project-tech">{p["tech"]}</span> — {p["description"]}</p>\n'

    skills_rows = ""
    skills = resume["skills"]
    for i in range(0, len(skills), 2):
        left = skills[i]
        right = skills[i + 1] if i + 1 < len(skills) else None
        right_td = f'<td><span class="skill-label">{right["label"]}:</span> {right["items"]}</td>' if right else "<td></td>"
        skills_rows += f'  <tr><td><span class="skill-label">{left["label"]}:</span> {left["items"]}</td>{right_td}</tr>\n'

    edu_html = ""
    for edu in resume["education"]:
        edu_html += f"""
  <div class="edu-header"><span class="edu-school">{edu['school']}</span><span class="edu-loc">{edu['location']}</span></div>
  <div class="edu-header"><span class="edu-degree">{edu['degree']}</span><span class="edu-dates">{edu['dates']}</span></div>
  <br>"""

    body = f"""<h1>{c['name']}</h1>
<div class="contact">
  {c['email']} &nbsp;·&nbsp; {c['phone']} &nbsp;·&nbsp;
  <a href="https://{c['linkedin']}">{c['linkedin']}</a>
</div>
<hr>

<h2>Professional Summary</h2>
<p class="summary">{resume['summary']}</p>

<h2>Experience</h2>
{exp_html}

<h2>Projects</h2>
{proj_html}

<h2>Education</h2>
{edu_html}

<h2>Skills</h2>
<table class="skills-table">
{skills_rows}</table>

<p style="font-size:8.5pt;color:#aaa;margin-top:18px;border-top:1px solid #eee;padding-top:6px">
  Tailored for: {job.get('company')} — {job.get('title')} &nbsp;·&nbsp; Generated {datetime.now().strftime('%Y-%m-%d')}
</p>"""

    return """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<title>Lokesh Arora — Resume</title>
<style>
  * { margin: 0; padding: 0; box-sizing: border-box; }
  body {
    font-family: 'Georgia', 'Times New Roman', serif;
    font-size: 10.5pt;
    line-height: 1.4;
    color: #111;
    max-width: 780px;
    margin: 0 auto;
    padding: 36px 40px;
  }
  h1 { font-size: 22pt; font-variant: small-caps; letter-spacing: 0.02em; margin-bottom: 4px; }
  .contact { font-size: 9.5pt; color: #333; margin-bottom: 14px; }
  .contact a { color: #1a73e8; text-decoration: none; }
  hr { border: none; border-top: 1px solid #111; margin: 8px 0 10px; }
  h2 { font-size: 11pt; font-variant: small-caps; letter-spacing: 0.08em; border-bottom: 1px solid #111; padding-bottom: 2px; margin: 14px 0 8px; }
  .summary { font-size: 10pt; margin-bottom: 4px; }
  .job-header { display: flex; justify-content: space-between; align-items: baseline; margin-bottom: 1px; }
  .job-company { font-weight: bold; }
  .job-location { font-size: 9.5pt; color: #333; }
  .job-title { font-style: italic; font-size: 9.5pt; }
  .job-dates { font-size: 9.5pt; color: #333; font-style: italic; }
  .job-entry { margin-bottom: 9px; }
  ul { margin: 3px 0 0 18px; }
  li { margin-bottom: 2px; font-size: 10pt; }
  .project-title { font-weight: bold; }
  .project-tech { font-style: italic; }
  .skills-table { width: 100%; border-collapse: collapse; }
  .skills-table td { vertical-align: top; padding: 1px 6px 2px 0; font-size: 10pt; width: 50%; }
  .skill-label { font-weight: bold; }
  .edu-header { display: flex; justify-content: space-between; align-items: baseline; }
  .edu-school { font-weight: bold; }
  .edu-loc { font-size: 9.5pt; color: #333; }
  .edu-degree { font-style: italic; font-size: 9.5pt; }
  .edu-dates { font-size: 9.5pt; color: #333; font-style: italic; }
  @media print { body { padding: 0; margin: 0; } }
</style>
</head>
<body>
""" + body + "\n</body>\n</html>"


# ── Fetcher ───────────────────────────────────────────────────────────────────

HEADERS = {"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) Safari/537.36"}

def fetch_job_description(url: str) -> str:
    try:
        req = Request(url, headers=HEADERS)
        with urlopen(req, timeout=12) as r:
            html = r.read().decode("utf-8", errors="ignore")
        html = re.sub(r'<(script|style)[^>]*>.*?</\1>', ' ', html, flags=re.DOTALL | re.IGNORECASE)
        text = re.sub(r'<[^>]+>', ' ', html)
        return re.sub(r'\s+', ' ', text).strip()[:5000]
    except Exception as e:
        log.debug(f"JD fetch failed {url}: {e}")
        return ""


# ── Public API ────────────────────────────────────────────────────────────────

def safe_filename(company: str, title: str) -> str:
    raw = f"{company}_{title}"
    clean = re.sub(r'[^a-zA-Z0-9_\-]', '_', raw)
    return re.sub(r'_+', '_', clean).strip('_')[:80]


def generate_and_save_resume(job: dict) -> Path | None:
    company = job.get("company", "Unknown")
    title = job.get("title", "Unknown")
    date_str = datetime.now().strftime("%Y-%m-%d")

    out_dir = RESUMES_DIR / date_str
    out_dir.mkdir(parents=True, exist_ok=True)

    fname = safe_filename(company, title) + ".html"
    out_path = out_dir / fname

    if out_path.exists():
        return out_path

    log.info(f"  Resume → {company} / {title}")
    jd_text = fetch_job_description(job.get("url", ""))
    tailored = build_tailored_resume(job, jd_text)
    html = render_html(tailored)
    out_path.write_text(html, encoding="utf-8")
    return out_path


def generate_resumes_for_jobs(jobs: list[dict]) -> list[Path]:
    RESUMES_DIR.mkdir(exist_ok=True)
    saved = []
    for job in jobs:
        try:
            p = generate_and_save_resume(job)
            if p:
                saved.append(p)
        except Exception as e:
            log.error(f"Resume failed for {job.get('company')}: {e}")
    log.info(f"Resumes saved: {len(saved)}/{len(jobs)}")
    return saved
