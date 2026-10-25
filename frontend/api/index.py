import os, io, re, json
import requests
from fastapi import FastAPI, UploadFile, File
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pypdf import PdfReader
import docx
from docx.shared import Pt
from docx.enum.text import WD_ALIGN_PARAGRAPH

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

NOISY_SKILLS = {"c", "english", "communication", "problem solving", "computer engineering", "marketing", "sales"}

# عائلات التخصصات لضمان مطابقة عنوان الوظيفة مع تخصص الـ CV بنسبة 100%
ROLE_FAMILIES = {
    "ai_data": {
        "triggers": ["ai", "machine learning", "data", "deep learning", "nlp", "computer vision", "artificial intelligence", "ml"],
        "valid_titles": ["ai", "machine learning", "ml", "data", "nlp", "vision", "deep learning", "research", "python", "scientist", "analytics", "analyst", "llm", "genai"],
        "banned_titles": ["frontend", "front-end", "front end", "react", "angular", "vue", "rails", "ruby", "php", "laravel", "wordpress", "ios", "android", "flutter", "full stack", "fullstack", "full-stack", "back-end", "backend", "back end", "ui/ux", "sales", "marketing", "recruiter", "hr", "customer", "support", "accountant", ".net", "c#", "java "]
    },
    "frontend": {
        "triggers": ["frontend", "front-end", "react", "angular", "vue", "ui"],
        "valid_titles": ["frontend", "front-end", "front end", "react", "angular", "vue", "javascript", "typescript", "ui", "web"],
        "banned_titles": ["backend", "back-end", "data scientist", "machine learning", "ai ", "devops", "security", "ios", "android"]
    },
    "backend": {
        "triggers": ["backend", "back-end", "node", "django", "spring", "laravel", "php"],
        "valid_titles": ["backend", "back-end", "back end", "node", "python", "java", "golang", "go ", "php", "laravel", "django", "api", "software engineer"],
        "banned_titles": ["frontend", "front-end", "react", "ui/ux", "data analyst", "recruiter", "sales"]
    },
    "fullstack": {
        "triggers": ["full stack", "fullstack", "full-stack"],
        "valid_titles": ["full stack", "fullstack", "full-stack", "software engineer", "web developer", "react", "node"],
        "banned_titles": ["data analyst", "recruiter", "sales", "marketing", "support", "hr"]
    },
    "devops_cloud": {
        "triggers": ["devops", "cloud", "sre", "aws", "kubernetes", "infrastructure"],
        "valid_titles": ["devops", "cloud", "sre", "reliability", "infrastructure", "platform", "aws", "kubernetes", "docker", "system"],
        "banned_titles": ["frontend", "react", "ui/ux", "sales", "marketing"]
    },
    "cybersecurity": {
        "triggers": ["security", "cyber", "penetration", "soc", "infosec"],
        "valid_titles": ["security", "cyber", "soc", "penetration", "pentest", "infosec", "vulnerability", "network"],
        "banned_titles": ["frontend", "react", "sales", "marketing"]
    },
    "mobile": {
        "triggers": ["mobile", "android", "ios", "flutter", "react native"],
        "valid_titles": ["mobile", "android", "ios", "flutter", "react native", "swift", "kotlin"],
        "banned_titles": ["frontend", "backend", "data", "devops"]
    }
}

def detect_family(role_or_query: str, skills: list) -> str:
    combined = (role_or_query + " " + " ".join(skills[:10])).lower()
    for fam_key, fam_data in ROLE_FAMILIES.items():
        if any(trig in combined for trig in fam_data["triggers"]):
            return fam_key
    return "general"

def is_title_valid_for_family(title: str, family: str) -> bool:
    t_low = title.lower()
    if family not in ROLE_FAMILIES:
        # فلتر عام ضد الوظائف غير التقنية
        general_banned = ["sales", "marketing", "recruiter", "hr", "customer support", "accountant", "copywriter"]
        return not any(b in t_low for b in general_banned)
    
    fam = ROLE_FAMILIES[family]
    # 1. استبعاد فوري إذا كان العنوان يحتوي على كلمة محظورة لهذا التخصص
    if any(bad in t_low for bad in fam["banned_titles"]):
        return False
    # 2. يجب أن يحتوي العنوان على كلمة واحدة على الأقل تدل على التخصص
    if any(valid in t_low for valid in fam["valid_titles"]):
        return True
    return False

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
        except Exception:
            pass
    elif fname.endswith(".docx"):
        try:
            doc = docx.Document(io.BytesIO(file_bytes))
            for p in doc.paragraphs:
                text += p.text + "\n"
        except Exception:
            pass
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

    return ranked_skills, best_class

def fetch_targeted_jobs(search_query: str, top_skills: list, country: str = "eg", strict_family: str = None):
    jobs = []
    seen_titles = set()

    family = strict_family or detect_family(search_query, top_skills)

    # تحديد كلمات بحث دقيقة جداً للـ API حسب عائلة التخصص
    if family == "ai_data":
        queries = ["machine learning", "artificial intelligence", "data scientist", "data analyst", "nlp", "computer vision", "ai engineer"]
    elif family == "frontend":
        queries = ["frontend", "react developer", "front-end"]
    elif family == "backend":
        queries = ["backend", "python developer", "nodejs"]
    elif family == "fullstack":
        queries = ["full stack", "fullstack"]
    elif family == "devops_cloud":
        queries = ["devops", "cloud engineer", "sre"]
    elif family == "cybersecurity":
        queries = ["cybersecurity", "security engineer", "soc"]
    elif family == "mobile":
        queries = ["mobile developer", "flutter", "ios", "android"]
    else:
        queries = [search_query] + top_skills[:2]

    for q in queries:
        if not q or len(q.strip()) < 2:
            continue
        try:
            r = requests.get(f"https://remotive.com/api/remote-jobs?search={q.strip()}&limit=35", timeout=7)
            if r.status_code == 200:
                for item in r.json().get("jobs", []):
                    title = item.get("title", "")
                    
                    # تطبيق الفلتر الصارم على عنوان الوظيفة
                    if not is_title_valid_for_family(title, family):
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

def rank_and_filter_jobs(jobs, user_skills, user_exp, user_level, user_role=""):
    if not jobs:
        return []

    all_user_skills = {s.lower().strip() for s in user_skills}
    family = detect_family(user_role, user_skills)
    ranked = []

    for job in jobs:
        title_lower = job["Title"].lower()
        desc_lower = job.get("Full_Text", (title_lower + " " + job["Description"]).lower())

        # التأكد مرة ثانية من صلاحية العنوان
        if not is_title_valid_for_family(title_lower, family):
            continue

        job_skills = {s for s in VOCAB.keys() if s not in NOISY_SKILLS and re.search(skill_regex(s), desc_lower)}
        matched_all = sorted([s for s in job_skills if s in all_user_skills])
        missing = sorted(list(job_skills - all_user_skills))[:6]

        # 1. حساب حقيقي لنسبة المهارات (Skill_Pct)
        total_job_skills = max(len(job_skills), 1)
        raw_skill_ratio = len(matched_all) / min(total_job_skills, 10)
        skill_pct = int(min(max(raw_skill_ratio * 100, 35), 98))
        
        # مكافأة إذا كان عنوان الوظيفة يطابق التخصص بدقة
        if family in ROLE_FAMILIES and any(v in title_lower for v in ROLE_FAMILIES[family]["valid_titles"][:6]):
            skill_pct = min(skill_pct + 12, 98)

        # 2. حساب حقيقي لنسبة المستوى الوظيفي (Level_Pct) بناءً على العنوان
        is_job_senior = any(w in title_lower for w in ["senior", "sr.", "sr ", "lead", "principal", "staff", "head", "director", "manager"])
        is_job_junior = any(w in title_lower for w in ["junior", "jr.", "jr ", "entry", "intern", "graduate", "associate"])

        u_lvl = user_level.lower()
        if "student" in u_lvl or "entry" in u_lvl:
            if is_job_junior:
                level_pct = 96
            elif is_job_senior:
                level_pct = 55  # تقليل النسبة لأن الوظيفة Senior والمستخدم Entry Level
            else:
                level_pct = 84
        elif "experienced" in u_lvl or "mid" in u_lvl:
            if is_job_senior:
                level_pct = 86
            elif is_job_junior:
                level_pct = 75
            else:
                level_pct = 94
        else:
            level_pct = 92 if is_job_senior else 78

        # 3. حساب حقيقي لنسبة الخبرة (Exp_Pct) بناءً على السنوات المطلوبة في الوصف
        req_exp_matches = re.findall(r'(\d+)\+?\s*(?:years?|yrs?)', desc_lower)
        req_years = [int(x) for x in req_exp_matches if 1 <= int(x) <= 15]
        if req_years:
            job_req_exp = min(req_years)
            diff = float(user_exp) - job_req_exp
            if diff >= 0:
                exp_pct = 95
            else:
                exp_pct = int(max(95 - (abs(diff) * 10), 50))
        else:
            exp_pct = 88 if not is_job_senior else (65 if float(user_exp) < 3 else 92)

        # 4. الحساب النهائي الموزون لـ Match_Score
        match_score = int((skill_pct * 0.55) + (exp_pct * 0.25) + (level_pct * 0.20))
        match_score = min(max(match_score, 45), 98)

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

    ranked = sorted(ranked, key=lambda x: x["Match_Score"], reverse=True)
    return ranked[:10]

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

    family = detect_family(role, skills)
    jobs = fetch_targeted_jobs(role, skills, country, strict_family=family)
    return {"jobs": rank_and_filter_jobs(jobs, skills, exp, level, role)}

@app.post("/api/manual-recommendations")
async def manual_recs(payload: dict):
    skills_str = payload.get("skills", "")
    skills = [s.strip().lower() for s in re.split(r'[,;]', skills_str) if s.strip()]
    exp = payload.get("experience_years", 2)
    level = payload.get("career_level", "Entry Level")
    country = payload.get("country_code", "eg")

    family = detect_family(skills_str, skills)
    query = skills[0] if skills else "Developer"
    jobs = fetch_targeted_jobs(query, skills, country, strict_family=family)
    return {"jobs": rank_and_filter_jobs(jobs, skills, exp, level, skills_str)}

@app.get("/api/live-jobs")
async def live_jobs(query: str = "AI Engineer", country: str = "eg"):
    family = detect_family(query, [query])
    jobs = fetch_targeted_jobs(query, [], country, strict_family=family)
    return {"jobs": [{k: v for k, v in j.items() if k != "Full_Text"} for j in jobs[:15]]}

@app.post("/api/build-cv")
async def build_cv(data: dict):
    doc = docx.Document()
    name_p = doc.add_paragraph()
    name_p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    r_name = name_p.add_run(data.get("name", "Your Name"))
    r_name.bold = True
    r_name.font.size = Pt(20)

    title_p = doc.add_paragraph()
    title_p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    title_p.add_run(data.get("title", "")).font.size = Pt(12)

    contact_p = doc.add_paragraph()
    contact_p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    contact_p.add_run(f"{data.get('email', '')} | {data.get('phone', '')} | {data.get('linkedin', '')}").font.size = Pt(10)

    for heading, key in [("SUMMARY", "summary"), ("EXPERIENCE", "experience"), ("PROJECTS", "projects"), ("EDUCATION", "education"), ("SKILLS", "skills"), ("LANGUAGES", "languages")]:
        val = data.get(key, "").strip()
        if val:
            doc.add_heading(heading, level=2)
            for line in val.split("\n"):
                if line.strip():
                    doc.add_paragraph(line.strip())

    bio = io.BytesIO()
    doc.save(bio)
    bio.seek(0)
    return StreamingResponse(bio, media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document")
