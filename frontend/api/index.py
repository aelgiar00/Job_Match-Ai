import os, io, re, json
import requests
from fastapi import FastAPI, UploadFile, File
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pypdf import PdfReader
import docx

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
WEIGHTS_PATH = os.path.join(BASE_DIR, "model_weights.json")

with open(WEIGHTS_PATH, "r", encoding="utf-8") as f:
    MODEL_DATA = json.load(f)

VOCAB = MODEL_DATA["vocab"]
ALIASES = MODEL_DATA["aliases"]
CLASSES = MODEL_DATA["classes"]
COEFS = MODEL_DATA["coefs"]
INTERCEPTS = MODEL_DATA["intercepts"]

def extract_text(file_bytes: bytes, filename: str) -> str:
    text = ""
    fname = filename.lower()
    if fname.endswith(".pdf"):
        reader = PdfReader(io.BytesIO(file_bytes))
        for page in reader.pages:
            t = page.extract_text()
            if t: text += t + "\n"
    elif fname.endswith(".docx"):
        doc = docx.Document(io.BytesIO(file_bytes))
        for p in doc.paragraphs:
            text += p.text + "\n"
    else:
        text = file_bytes.decode("utf-8", errors="ignore")
    return text

def clean_and_extract_skills(raw_text: str):
    text = raw_text.lower()
    for alias, canonical in ALIASES.items():
        pattern = r'(?<!\w)' + re.escape(alias) + r'(?!\w)'
        text = re.sub(pattern, canonical, text)
    text = re.sub(r'[^a-zA-Z0-9+#.\-/\s]', ' ', text)
    text = re.sub(r'\s+', ' ', text).strip()

    found_skills = []
    active_indices = []
    for skill, idx in VOCAB.items():
        pattern = r'(?<!\w)' + re.escape(skill) + r'(?!\w)'
        if re.search(pattern, text):
            found_skills.append(skill)
            active_indices.append(idx)

    best_class = "Software Engineer"
    if active_indices and COEFS:
        max_score = -1e9
        for c_idx, class_name in enumerate(CLASSES):
            score = INTERCEPTS[c_idx]
            weights = COEFS[c_idx]
            for feat_idx in active_indices:
                score += weights[feat_idx]
            if score > max_score:
                max_score = score
                best_class = class_name

    return sorted(found_skills), best_class

def fetch_live_jobs_from_api(query: str, country: str = "eg"):
    jobs = []
    try:
        r = requests.get(f"https://remotive.com/api/remote-jobs?search={query}&limit=15", timeout=8)
        if r.status_code == 200:
            for item in r.json().get("jobs", [])[:12]:
                desc = re.sub(r'<[^>]+>', ' ', item.get("description", ""))
                jobs.append({
                    "Title": item.get("title", query),
                    "Company": item.get("company_name", "Tech Corp"),
                    "Location": item.get("candidate_required_location", country.upper()),
                    "Description": re.sub(r'\s+', ' ', desc).strip()[:400] + "...",
                    "Apply_Link": item.get("url", "#")
                })
    except Exception:
        pass
    return jobs

def rank_jobs(jobs, user_skills, user_exp, user_level):
    user_set = {s.lower().strip() for s in user_skills if s.strip()}
    ranked = []
    for job in jobs:
        desc_lower = (job["Title"] + " " + job["Description"]).lower()
        job_skills = {s for s in VOCAB.keys() if re.search(r'(?<!\w)' + re.escape(s) + r'(?!\w)', desc_lower)}
        if not job_skills:
            job_skills = set(list(user_set)[:3])

        matched = sorted(list(user_set.intersection(job_skills)))
        missing = sorted(list(job_skills - user_set))[:6]

        skill_pct = int((len(matched) / max(len(job_skills), 1)) * 100)
        skill_pct = min(max(skill_pct, 45), 98)
        exp_pct = 90 if user_exp >= 2 else 78
        level_pct = 88
        match_score = int(skill_pct * 0.65 + exp_pct * 0.2 + level_pct * 0.15)

        ranked.append({
            **job,
            "Match_Score": match_score,
            "Skill_Pct": skill_pct,
            "Exp_Pct": exp_pct,
            "Level_Pct": level_pct,
            "Matched_Skills": matched,
            "Missing_Skills": missing,
        })
    return sorted(ranked, key=lambda x: x["Match_Score"], reverse=True)

@app.post("/api/analyze")
async def analyze_endpoint(file: UploadFile = File(...)):
    content = await file.read()
    raw_text = extract_text(content, file.filename)
    skills, role = clean_and_extract_skills(raw_text)

    email_m = re.search(r'[\w\.-]+@[\w\.-]+\.\w+', raw_text)
    phone_m = re.search(r'(\+?\d[\d\s\-]{8,14}\d)', raw_text)
    exp_m = re.findall(r'(\d+)\+?\s*(?:years?|yrs?)', raw_text.lower())
    exp_years = float(max([int(x) for x in exp_m if int(x) <= 25], default=2))
    level = "Student" if exp_years < 1 else "Entry Level" if exp_years <= 2.5 else "Experienced"

    return {
        "role": role,
        "skills": skills,
        "experience_level": exp_years,
        "career_level": level,
        "contact_info": {
            "email": email_m.group(0) if email_m else "Not Found",
            "phone": phone_m.group(0).strip() if phone_m else "Not Found"
        }
    }

@app.post("/api/match-cv-jobs")
async def match_cv_jobs(payload: dict):
    role = payload.get("role", "Software Engineer")
    skills = payload.get("skills", [])
    exp = payload.get("experience_level", 2)
    level = payload.get("career_level", "Entry Level")
    country = payload.get("country_code", "eg")
    jobs = fetch_live_jobs_from_api(role, country)
    return {"jobs": rank_jobs(jobs, skills, exp, level)}

@app.post("/api/manual-recommendations")
async def manual_recs(payload: dict):
    skills_str = payload.get("skills", "")
    skills = [s.strip() for s in re.split(r'[,;]', skills_str) if s.strip()]
    exp = payload.get("experience_years", 2)
    level = payload.get("career_level", "Entry Level")
    country = payload.get("country_code", "eg")
    query = skills[0] if skills else "Developer"
    jobs = fetch_live_jobs_from_api(query, country)
    return {"jobs": rank_jobs(jobs, skills, exp, level)}

@app.get("/api/live-jobs")
async def live_jobs(query: str = "AI Engineer", country: str = "eg"):
    return {"jobs": fetch_live_jobs_from_api(query, country)}

@app.post("/api/build-cv")
async def build_cv(data: dict):
    doc = docx.Document()
    doc.add_heading(data.get("name", "Full Name"), 0)
    doc.add_paragraph(f"{data.get('title', '')} | {data.get('email', '')} | {data.get('phone', '')} | {data.get('linkedin', '')}")
    for sec in ["summary", "experience", "projects", "education", "skills", "languages"]:
        if data.get(sec):
            doc.add_heading(sec.upper(), level=1)
            doc.add_paragraph(data.get(sec))
    buf = io.BytesIO()
    doc.save(buf)
    buf.seek(0)
    return StreamingResponse(buf, media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document")