"""
Job Hunter AI — Backend
Fetches jobs from Adzuna API, normalizes data, exposes /api/jobs
"""

import os, requests, random
from flask import Flask, jsonify, request
from datetime import datetime
from dotenv import load_dotenv
load_dotenv()

app = Flask(__name__)

# ── Adzuna credentials ────────────────────────────────────────────────────────
ADZUNA_APP_ID  = os.getenv("ADZUNA_APP_ID",  "YOUR_APP_ID")
ADZUNA_APP_KEY = os.getenv("ADZUNA_APP_KEY", "YOUR_APP_KEY")
ADZUNA_BASE    = "https://api.adzuna.com/v1/api/jobs"

# ── Role → keyword mapping ────────────────────────────────────────────────────
ROLE_KEYWORDS = {
    "Product":              "product manager",
    "Product Manager":      "product manager",
    "Software Engineer":    "software engineer",
    "Frontend Engineer":    "frontend developer",
    "Backend Engineer":     "backend developer",
    "Full Stack Engineer":  "full stack developer",
    "Data Scientist":       "data scientist",
    "Data Analyst":         "data analyst",
    "ML Engineer":          "machine learning engineer",
    "DevOps Engineer":      "devops engineer",
    "Designer":             "ux ui designer",
    "Marketing":            "marketing manager",
    "Sales":                "sales manager",
    "HR":                   "human resources",
    "Finance":              "finance analyst",
}

# ── Experience keyword injection ──────────────────────────────────────────────
EXPERIENCE_KEYWORDS = {
    "entry":  "entry level junior",
    "mid":    "mid level",
    "senior": "senior lead",
}

# ── Normalize a single Adzuna job ─────────────────────────────────────────────
def normalize(job: dict) -> dict:
    loc = job.get("location", {})
    area = loc.get("area", [])
    location = loc.get("display_name", "") or (", ".join(area[1:]) if len(area) > 1 else "")

    salary_min = job.get("salary_min")
    salary_max = job.get("salary_max")
    salary = ""
    if salary_min and salary_max:
        salary = f"₹{int(salary_min):,} – ₹{int(salary_max):,}"
    elif salary_min:
        salary = f"₹{int(salary_min):,}+"

    created = job.get("created", "")
    try:
        dt = datetime.fromisoformat(created.replace("Z", "+00:00"))
        posted_at = dt.strftime("%d %b %Y")
    except Exception:
        posted_at = created[:10] if len(created) >= 10 else ""

    return {
        "id":          job.get("id", ""),
        "title":       job.get("title", "").strip(),
        "company":     job.get("company", {}).get("display_name", "Unknown"),
        "location":    location,
        "description": job.get("description", "").strip()[:400],
        "url":         job.get("redirect_url", ""),
        "salary":      salary,
        "posted_at":   posted_at,
        "category":    job.get("category", {}).get("label", ""),
    }

# ── /api/jobs ─────────────────────────────────────────────────────────────────
@app.route("/api/jobs")
def get_jobs():
    role        = request.args.get("role",       "software engineer")
    location    = request.args.get("location",   "india")
    per_page    = request.args.get("per_page",   "50")
    # Filters
    days_old    = request.args.get("days_old",   "")     # 1 / 3 / 7 / 30
    exp_filter  = request.args.get("experience", "")     # entry / mid / senior
    loc_filter  = request.args.get("loc_filter", "")     # free-text location override
    # Freshness: client passes a random page (1-5) each refresh
    page        = request.args.get("page",       str(random.randint(1, 4)))

    # Build keyword
    keyword = ROLE_KEYWORDS.get(role, role)
    if exp_filter and exp_filter in EXPERIENCE_KEYWORDS:
        keyword = f"{EXPERIENCE_KEYWORDS[exp_filter]} {keyword}"

    # Location: prefer explicit loc_filter, fallback to profile location
    where = (loc_filter or location).replace(", India", "").replace(" India", "").strip() or "india"

    params = {
        "app_id":           ADZUNA_APP_ID,
        "app_key":          ADZUNA_APP_KEY,
        "what":             keyword,
        "where":            where,
        "results_per_page": int(per_page),
    }
    if days_old:
        params["max_days_old"] = int(days_old)

    try:
        resp = requests.get(
            f"{ADZUNA_BASE}/in/search/{page}",
            params=params,
            timeout=10
        )
        resp.raise_for_status()
        data  = resp.json()
        jobs  = [normalize(j) for j in data.get("results", [])]
        total = data.get("count", len(jobs))
        return jsonify({
            "jobs":    jobs,
            "total":   total,
            "page":    int(page),
            "keyword": keyword,
        })
    except requests.exceptions.HTTPError as e:
        return jsonify({"error": str(e), "jobs": [], "total": 0}), 502
    except Exception as e:
        return jsonify({"error": str(e), "jobs": [], "total": 0}), 500

# ── /api/health ───────────────────────────────────────────────────────────────
@app.route("/api/health")
def health():
    return jsonify({"status": "ok", "adzuna_configured": ADZUNA_APP_ID != "YOUR_APP_ID"})

if __name__ == "__main__":
    port = int(os.getenv("PORT", 8080))
    print(f"🚀  Job Hunter AI backend running on http://0.0.0.0:{port}")
    app.run(host="0.0.0.0", port=port, debug=False)
