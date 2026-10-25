import os, io, re, json
import requests
from fastapi import FastAPI, UploadFile, File
from fastapi.middleware.cors import CORSMiddleware
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

NOISY_SKILLS = {"c", "english", "communication", "problem solving", "computer engineering"}

def skill_regex(skill: str) -> str:
    esc = re.escape(skill)
    return r'(?<![a-zA-Z0-9+#.\-/])' + esc + r'(?![a-zA-Z0-9+#.\-/])'

def extract_text(file_bytes: bytes, filename: str) -> str:
    text = ""
    fname = filename.lower()
    
    if fname.endswith(".pdf"):
        try:
            reader = PdfReader(io.BytesIO(file_bytes))
            for page in reader.pages:
                t = page.extract_text()
                if t: text += t + "\n"
        except Exception as e:
            print(f"Error parsing PDF: {e}")
            
    elif fname.endswith(".docx"):
        try:
            doc = docx.Document(io.BytesIO(file_bytes))
            for p in doc.paragraphs:
                text += p.text + "\n"
        except Exception as e:
            print(f"Error parsing DOCX: {e}")
            
    else:
        text = file_bytes.decode("utf-8", errors="ignore")
        
    return text

def clean_and_extract_skills(raw_text: str):
    text = raw_text.lower()
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

    for skill, idx in VOCAB.items():
        if skill in NOISY_SKILLS:
            continue
        pattern = skill_regex(skill)
        matches = re.findall(pattern, text)
        if matches:
            header_bonus = 4 if re.search(pattern, header_text) else 0
            weight = len(matches) + header_bonus
            skill_weights[skill] = weight
            active_indices[idx] = weight

    ranked_skills = sorted(skill_weights.keys(), key=lambda s: skill_weights[s], reverse=True)

    best_class = "Software / AI Developer"
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

    return ranked_skills, best_class

def fetch_targeted_jobs(search_query: str, top_skills: list, country: str = "eg"):
    jobs = []
    seen_titles = set()

    sq_lower = search_query.lower()
    queries = []
    
    # 1. التوجيه الذكي للبحث في الـ API بالتخصص فقط (بدون الاعتماد على المهارات الفردية اللي بتلخبط النتايج)
    if any(x in sq_lower for x in ["ai", "machine", "data", "deep", "nlp", "vision"]):
        queries = ["AI", "Machine Learning", "Data Scientist", "NLP"]
    elif any(x in sq_lower for x in ["front", "ui", "ux"]):
        queries = ["Frontend", "React", "UI"]
    elif any(x in sq_lower for x in ["back", "api", "node"]):
        queries = ["Backend", "Backend Developer"]
    elif any(x in sq_lower for x in ["full", "stack"]):
        queries = ["Full Stack", "Fullstack"]
    elif any(x in sq_lower for x in ["cloud", "devops"]):
        queries = ["DevOps", "Cloud"]
    else:
        clean_q = re.sub(r'[^a-zA-Z0-9\s]', ' ', search_query).strip()
        queries = [clean_q]

    for q in set(queries):
        if not q or len(q.strip()) < 2:
            continue
        try:
            r = requests.get(f"https://remotive.com/api/remote-jobs?search={q.strip()}&limit=20", timeout=7)
            if r.status_code == 200:
                for item in r.json().get("jobs", []):
                    title = item.get("title", "")
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

def rank_and_filter_jobs(jobs, user_skills, user_exp, user_level, user_role=""):
    if not user_skills:
        return jobs[:6] if jobs else []

    all_user_skills = {s.lower().strip() for s in user_skills}
    ranked = []
    
    user_role_lower = user_role.lower()
    
    # تحديد تخصص المستخدم لتطبيق نظام العقاب/المكافأة
    is_ai = any(x in user_role_lower for x in ["ai", "machine", "data", "nlp", "vision"])
    is_back = any(x in user_role_lower for x in ["back", "node", "django", "laravel", "api"])
    is_front = any(x in user_role_lower for x in ["front", "ui", "ux", "react"])
    is_full = any(x in user_role_lower for x in ["full", "stack"])

    for job in jobs:
        title_lower = job["Title"].lower()
        desc_lower = job.get("Full_Text", (title_lower + " " + job["Description"]).lower())
        
        job_skills = {s for s in VOCAB.keys() if s not in NOISY_SKILLS and re.search(skill_regex(s), desc_lower)}
        matched_all = sorted([s for s in job_skills if s in all_user_skills])
        missing = sorted(list(job_skills - all_user_skills))[:5]

        match_score = 40 + (len(matched_all) * 8)
        
        # 2. نظام العقاب والمكافأة الديناميكي بناءً على التخصص
        if is_ai:
            if any(x in title_lower for x in ["ai", "machine", "data", "nlp", "vision"]):
                match_score += 25
            elif any(x in title_lower for x in ["backend", "full stack", "fullstack", "frontend", "web"]):
                match_score -= 40 # عقاب قوي للوظائف التي لا تنتمي للمجال
                
        elif is_back:
            if any(x in title_lower for x in ["backend", "back end"]):
                match_score += 25
            elif any(x in title_lower for x in ["frontend", "data", "ai", "machine"]):
                match_score -= 40
                
        elif is_front:
            if any(x in title_lower for x in ["frontend", "front end", "react", "vue"]):
                match_score += 25
            elif any(x in title_lower for x in ["backend", "data", "ai"]):
                match_score -= 40
                
        elif is_full:
            if any(x in title_lower for x in ["full stack", "fullstack"]):
                match_score += 25

        # تحديد الحد الأدنى والأقصى للسكور
        match_score = min(max(match_score, 10), 98)
        
        # طرد الوظائف التي قل السكور الخاص بها عن 40 بسبب نظام العقاب
        if match_score < 40:
            continue

        job_clean = {k: v for k, v in job.items() if k != "Full_Text"}
        ranked.append({
            **job_clean,
            "Match_Score": int(match_score),
            "Skill_Pct": int(match_score),
            "Exp_Pct": 90,
            "Level_Pct": 88,
            "Matched_Skills": matched_all,
            "Missing_Skills": missing,
        })

    # ترتيب الوظائف تنازلياً حسب أعلى مطابقة
    ranked = sorted(ranked, key=lambda x: x["Match_Score"], reverse=True)
    return ranked[:6]

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
    role = payload.get("role", "Software Engineer")
    skills = payload.get("skills", [])
    exp = payload.get("experience_level", 1.5)
    level = payload.get("career_level", "Entry Level")
    country = payload.get("country_code", "eg")

    jobs = fetch_targeted_jobs(role, skills, country)
    return {"jobs": rank_and_filter_jobs(jobs, skills, exp, level, role)}

@app.post("/api/manual-recommendations")
async def manual_recs(payload: dict):
    skills_str = payload.get("skills", "")
    skills = [s.strip().lower() for s in re.split(r'[,;]', skills_str) if s.strip()]
    exp = payload.get("experience_years", 2)
    level = payload.get("career_level", "Entry Level")
    country = payload.get("country_code", "eg")

    query = skills[0] if skills else "Developer"
    jobs = fetch_targeted_jobs(query, skills, country)
    return {"jobs": rank_and_filter_jobs(jobs, skills, exp, level, query)}

@app.get("/api/live-jobs")
async def live_jobs(query: str = "Developer", country: str = "eg"):
    jobs = fetch_targeted_jobs(query, [], country)
    return {"jobs": [{k: v for k, v in j.items() if k != "Full_Text"} for j in jobs[:10]]}

@app.post("/api/build-cv")
async def build_cv(data: dict):
    return {"status": "success"}
