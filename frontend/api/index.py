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

# مهارات عامة أو خادعة لا يجب أن تقود عملية البحث عن الوظائف بمفردها
NOISY_SKILLS = {"c", "english", "communication", "problem solving", "computer engineering"}

def skill_regex(skill: str) -> str:
    """بناء Regex دقيق يمنع تطابق حرف C مع C++ أو B.Sc."""
    esc = re.escape(skill)
    return r'(?<![a-zA-Z0-9+#.\-/])' + esc + r'(?![a-zA-Z0-9+#.\-/])'

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
    # إزالة اختصار B.Sc حتى لا يُقرأ حرف c كمهارة برمجية
    text = re.sub(r'\bb\.?s\.?c\.?\b', 'bachelor', text)
    header_text = text[:600]

    for alias, canonical in ALIASES.items():
        pattern = skill_regex(alias)
        text = re.sub(pattern, canonical, text)
        header_text = re.sub(pattern, canonical, header_text)

    text = re.sub(r'[^a-zA-Z0-9+#.\-/\s]', ' ', text)
    text = re.sub(r'\s+', ' ', text).strip()

    skill_weights = {}
    active_indices = {}

    # مهارات الذكاء الاصطناعي والبايثون تاخد أولوية قصوى لو موجودة في الـ CV
    priority_ai_skills = {
        "python", "machine learning", "deep learning", "artificial intelligence",
        "scikit-learn", "pytorch", "tensorflow", "nlp", "computer vision",
        "pandas", "numpy", "fastapi", "sql", "data science", "keras"
    }

    for skill, idx in VOCAB.items():
        if skill in NOISY_SKILLS:
            continue
        pattern = skill_regex(skill)
        matches = re.findall(pattern, text)
        if matches:
            header_bonus = 4 if re.search(pattern, header_text) else 0
            ai_bonus = 5 if skill in priority_ai_skills else 0
            weight = len(matches) + header_bonus + ai_bonus
            skill_weights[skill] = weight
            active_indices[idx] = weight

    ranked_skills = sorted(skill_weights.keys(), key=lambda s: skill_weights[s], reverse=True)

    best_class = "Machine Learning / AI"
    if active_indices and COEFS:
        max_score = -1e9
        for c_idx, class_name in enumerate(CLASSES):
            score = INTERCEPTS[c_idx]
            weights = COEFS[c_idx]
            for feat_idx, count_weight in active_indices.items():
                score += weights[feat_idx] * min(count_weight, 5)
            if score > max_score:
                max_score = score
                best_class = class_name

    top_str = " ".join(ranked_skills[:6])
    if any(k in top_str for k in ["machine learning", "scikit-learn", "pytorch", "tensorflow", "artificial intelligence"]):
        best_class = "Machine Learning / AI"

    return ranked_skills, best_class

def fetch_targeted_jobs(role: str, top_skills: list, country: str = "eg"):
    jobs = []
    seen_titles = set()

    # كلمات بحث مركزة جداً على مجال المتقدم
    queries = ["machine learning", "ai engineer", "python", "data scientist"]
    if "machine learning" not in role.lower() and "ai" not in role.lower():
        queries = [role] + top_skills[:2]

    # استبعاد الوظائف غير التقنية أو البعيدة عن المجال
    excluded_title_words = [
        "assistant", "sales", "marketing", "customer", "recruiter",
        "accountant", "writer", "designer", "rails", "ruby", "ios", "android"
    ]

    for q in queries:
        try:
            r = requests.get(f"https://remotive.com/api/remote-jobs?search={q}&limit=20", timeout=7)
            if r.status_code == 200:
                for item in r.json().get("jobs", []):
                    title = item.get("title", "")
                    title_low = title.lower()

                    if any(bad in title_low for bad in excluded_title_words):
                        continue

                    comp = item.get("company_name", "Tech Corp")
                    key = f"{title}_{comp}".lower()
                    if key in seen_titles:
                        continue
                    seen_titles.add(key)

                    desc = re.sub(r'<[^>]+>', ' ', item.get("description", ""))
                    jobs.append({
                        "Title": title,
                        "Company": comp,
                        "Location": item.get("candidate_required_location", country.upper()),
                        "Description": re.sub(r'\s+', ' ', desc).strip()[:420] + "...",
                        "Full_Text": (title + " " + desc).lower(),
                        "Apply_Link": item.get("url", "#")
                    })
        except Exception:
            pass

    return jobs

def rank_and_filter_jobs(jobs, user_skills, user_exp, user_level):
    if not user_skills:
        return []

    # أول 10 مهارات هي المهارات الأساسية للمرشح
    core_skills = {s.lower().strip() for s in user_skills[:10]}
    all_user_skills = {s.lower().strip() for s in user_skills}

    ranked = []
    for job in jobs:
        desc_lower = job.get("Full_Text", (job["Title"] + " " + job["Description"]).lower())
        title_lower = job["Title"].lower()

        job_skills = {
            s for s in VOCAB.keys()
            if s not in NOISY_SKILLS and re.search(skill_regex(s), desc_lower)
        }
        if not job_skills:
            continue

        matched_all = sorted([s for s in job_skills if s in all_user_skills])
        matched_core = [s for s in matched_all if s in core_skills]

        # شرط صارم: يجب أن تتطابق الوظيفة مع مهارتين على الأقل من مهاراتك الأساسية (مثل Python + ML)
        if len(matched_core) < 2:
            continue

        missing = sorted(list(job_skills - all_user_skills))[:5]

        # حساب نسبة تطابق المهارات بشكل واقعي ومتدرج
        ratio = len(matched_all) / max(len(job_skills), 1)
        title_Relevance = 18 if any(k in title_lower for k in ["ai", "machine learning", "ml", "data", "python"]) else 0
        skill_pct = min(int(ratio * 75) + title_Relevance + (len(matched_core) * 4), 97)
        skill_pct = max(skill_pct, 60)

        # لو الوظيفة طالبة Senior أو Lead والمتقدم Entry Level نقلل نسبة الـ Level Fit
        is_senior_job = any(w in title_lower for w in ["senior", "lead", "principal", "staff", "director"])
        exp_pct = 75 if (is_senior_job and user_exp < 3) else 94
        level_pct = 72 if (is_senior_job and user_level in ["Student", "Entry Level"]) else 92

        match_score = int(skill_pct * 0.70 + exp_pct * 0.15 + level_pct * 0.15)

        job_clean = {k: v for k, v in job.items() if k != "Full_Text"}
        ranked.append({
            **job_clean,
            "Match_Score": match_score,
            "Skill_Pct": skill_pct,
            "Exp_Pct": exp_pct,
            "Level_Pct": level_pct,
            "Matched_Skills": matched_all,
            "Missing_Skills": missing,
        })

    ranked_sorted = sorted(ranked, key=lambda x: x["Match_Score"], reverse=True)
    return ranked_sorted[:6]

@app.post("/api/analyze")
async def analyze_endpoint(file: UploadFile = File(...)):
    content = await file.read()
    raw_text = extract_text(content, file.filename)
    skills, role = clean_and_extract_skills(raw_text)

    email_m = re.search(r'[\w\.-]+@[\w\.-]+\.\w+', raw_text)
    phone_m = re.search(r'(\+?\d[\d\s\-]{8,14}\d)', raw_text)
    exp_m = re.findall(r'(\d+)\+?\s*(?:years?|yrs?)', raw_text.lower())
    exp_years = float(max([int(x) for x in exp_m if int(x) <= 25], default=1.5))
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
    role = payload.get("role", "Machine Learning / AI")
    skills = payload.get("skills", [])
    exp = payload.get("experience_level", 1.5)
    level = payload.get("career_level", "Entry Level")
    country = payload.get("country_code", "eg")

    jobs = fetch_targeted_jobs(role, skills[:4], country)
    return {"jobs": rank_and_filter_jobs(jobs, skills, exp, level)}

@app.post("/api/manual-recommendations")
async def manual_recs(payload: dict):
    skills_str = payload.get("skills", "")
    skills = [s.strip().lower() for s in re.split(r'[,;]', skills_str) if s.strip()]
    exp = payload.get("experience_years", 2)
    level = payload.get("career_level", "Entry Level")
    country = payload.get("country_code", "eg")
    role = f"{skills[0]}" if skills else "Machine Learning"
    jobs = fetch_targeted_jobs(role, skills[:4], country)
    return {"jobs": rank_and_filter_jobs(jobs, skills, exp, level)}

@app.get("/api/live-jobs")
async def live_jobs(query: str = "Machine Learning", country: str = "eg"):
    jobs = fetch_targeted_jobs(query, [query], country)
    return {"jobs": [{k: v for k, v in j.items() if k != "Full_Text"} for j in jobs[:10]]}

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
