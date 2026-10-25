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
    # إعطاء وزن مضاعف لأول جزء في الـ CV (العنوان والملخص) لأنه يحدد التخصص الحقيقي
    header_text = text[:600]

    for alias, canonical in ALIASES.items():
        pattern = r'(?<!\w)' + re.escape(alias) + r'(?!\w)'
        text = re.sub(pattern, canonical, text)
        header_text = re.sub(pattern, canonical, header_text)

    text = re.sub(r'[^a-zA-Z0-9+#.\-/\s]', ' ', text)
    text = re.sub(r'\s+', ' ', text).strip()

    skill_weights = {}
    active_indices = {}

    for skill, idx in VOCAB.items():
        pattern = r'(?<!\w)' + re.escape(skill) + r'(?!\w)'
        matches = re.findall(pattern, text)
        if matches:
            # حساب وزن المهارة بناءً على تكرارها في المشاريع والخبرة + وجودها في عنوان الـ CV
            header_bonus = 3 if re.search(pattern, header_text) else 0
            weight = len(matches) + header_bonus
            skill_weights[skill] = weight
            active_indices[idx] = weight

    # ترتيب المهارات حسب الأهمية والتكرار في الـ CV (وليس أبجدياً!)
    ranked_skills = sorted(skill_weights.keys(), key=lambda s: skill_weights[s], reverse=True)

    # حساب التخصص (Role) مع مراعاة وزن كل مهارة
    best_class = "AI & Machine Learning Engineer"
    if active_indices and COEFS:
        max_score = -1e9
        for c_idx, class_name in enumerate(CLASSES):
            score = INTERCEPTS[c_idx]
            weights = COEFS[c_idx]
            for feat_idx, count_weight in active_indices.items():
                score += weights[feat_idx] * min(count_weight, 4)
            if score > max_score:
                max_score = score
                best_class = class_name

    # تحسين التسمية إذا كانت المهارات الأساسية تركز على الـ Machine Learning
    top_5_str = " ".join(ranked_skills[:6])
    if any(k in top_5_str for k in ["machine learning", "scikit-learn", "deep learning", "pytorch", "tensorflow", "nlp"]):
        if "software" in best_class.lower() or "data" in best_class.lower():
            best_class = "Machine Learning Engineer"

    return ranked_skills, best_class, skill_weights

def fetch_targeted_jobs(role: str, top_skills: list, country: str = "eg"):
    jobs = []
    seen_titles = set()

    # البحث بالتخصص الدقيق + أهم المهارات المتصدرة في الـ CV فقط
    search_queries = [role]
    if top_skills:
        search_queries.append(f"{top_skills[0]} {top_skills[1] if len(top_skills) > 1 else ''}".strip())
        if len(top_skills) > 2:
            search_queries.append(top_skills[2])

    for q in search_queries[:3]:
        try:
            r = requests.get(f"https://remotive.com/api/remote-jobs?search={q}&limit=12", timeout=7)
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
                        "Description": re.sub(r'\s+', ' ', desc).strip()[:450] + "...",
                        "Full_Text": (title + " " + desc).lower(),
                        "Apply_Link": item.get("url", "#")
                    })
        except Exception:
            pass

    return jobs

def rank_and_filter_jobs(jobs, user_skills, user_exp, user_level):
    if not user_skills:
        return []

    # المهارات الأساسية (أول 6 مهارات في الـ CV) تاخد ضعف الأهمية عن المهارات الفرعية (زي C++)
    core_skills = {s.lower().strip() for s in user_skills[:6]}
    secondary_skills = {s.lower().strip() for s in user_skills[6:]}
    all_user_skills = core_skills.union(secondary_skills)

    ranked = []
    for job in jobs:
        desc_lower = job.get("Full_Text", (job["Title"] + " " + job["Description"]).lower())
        title_lower = job["Title"].lower()

        # استخراج المهارات المطلوبة في الوظيفة
        job_skills = {s for s in VOCAB.keys() if re.search(r'(?<!\w)' + re.escape(s) + r'(?!\w)', desc_lower)}
        if not job_skills:
            continue

        matched_core = sorted([s for s in job_skills if s in core_skills])
        matched_sec = sorted([s for s in job_skills if s in secondary_skills])
        matched_all = matched_core + matched_sec

        # فلتر صارم: لازم الوظيفة تكون طالبة على الأقل مهارة أساسية واحدة أو مهارتين من الـ CV
        if len(matched_core) == 0 and len(matched_all) < 2:
            continue

        missing = sorted(list(job_skills - all_user_skills))[:5]

        # حساب نسبة التطابق بوزن أعلى للمهارات الأساسية وعنوان الوظيفة
        weighted_hits = (len(matched_core) * 2.0) + (len(matched_sec) * 0.7)
        title_bonus = 15 if any(cs in title_lower for cs in core_skills) else 0

        raw_skill_pct = int((weighted_hits / max(len(job_skills), 2)) * 85) + title_bonus
        skill_pct = min(max(raw_skill_pct, 55), 98)

        exp_pct = 92 if user_exp >= 1.5 else 82
        level_pct = 90
        match_score = int(skill_pct * 0.75 + exp_pct * 0.15 + level_pct * 0.10)

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

    # ترتيب تنازلي وإرجاع أفضل 6 وظائف مطابقة فقط لمنع الزحمة والعشوائية
    ranked_sorted = sorted(ranked, key=lambda x: (len(x["Matched_Skills"]), x["Match_Score"]), reverse=True)
    return ranked_sorted[:6]

@app.post("/api/analyze")
async def analyze_endpoint(file: UploadFile = File(...)):
    content = await file.read()
    raw_text = extract_text(content, file.filename)
    skills, role, _ = clean_and_extract_skills(raw_text)

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
    role = payload.get("role", "Machine Learning Engineer")
    skills = payload.get("skills", [])
    exp = payload.get("experience_level", 1.5)
    level = payload.get("career_level", "Entry Level")
    country = payload.get("country_code", "eg")

    # البحث باستخدام التخصص وأهم 3 مهارات متصدرة في الـ CV فقط
    jobs = fetch_targeted_jobs(role, skills[:3], country)
    return {"jobs": rank_and_filter_jobs(jobs, skills, exp, level)}

@app.post("/api/manual-recommendations")
async def manual_recs(payload: dict):
    skills_str = payload.get("skills", "")
    skills = [s.strip().lower() for s in re.split(r'[,;]', skills_str) if s.strip()]
    exp = payload.get("experience_years", 2)
    level = payload.get("career_level", "Entry Level")
    country = payload.get("country_code", "eg")
    role = f"{skills[0]} Developer" if skills else "Software Engineer"
    jobs = fetch_targeted_jobs(role, skills[:3], country)
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
