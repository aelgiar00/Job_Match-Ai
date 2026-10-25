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

# قواعد صارمة باستخدام Regex للكلمات الكاملة لمنع التداخل النصي وحظر وظائف Annotation/Trainer
ROLE_RULES = {
    "ai_data": {
        "triggers": [r"\bai\b", r"machine learning", r"\bml\b", r"data scien", r"deep learning", r"\bnlp\b", r"computer vision", r"artificial intelligence", r"data analy"],
        "valid_title_regex": r"\b(ai|ml|machine learning|data scientist|data science|data analyst|data engineer|deep learning|nlp|computer vision|artificial intelligence|llm|genai|mlops|python engineer)\b",
        "banned_title_regex": r"\b(trainer|annotation|annotator|rater|labeler|coding tasks|prompt writer|tutor|frontend|front-end|react|angular|vue|rails|ruby|php|laravel|wordpress|ios|android|flutter|full stack|fullstack|full-stack|back-end|backend|ui/ux|sales|marketing|recruiter|hr|support|accountant|\.net|c#)\b"
    },
    "frontend": {
        "triggers": [r"frontend", r"front-end", r"\breact\b", r"\bangular\b", r"\bvue\b"],
        "valid_title_regex": r"\b(frontend|front-end|front end|react|angular|vue|ui developer|web developer|javascript|typescript)\b",
        "banned_title_regex": r"\b(trainer|annotation|backend|back-end|data scientist|machine learning|devops|security|ios|android|sales|hr)\b"
    },
    "backend": {
        "triggers": [r"backend", r"back-end", r"\bnode\b", r"\bdjango\b", r"\bfastapi\b", r"\bspring\b", r"\blaravel\b"],
        "valid_title_regex": r"\b(backend|back-end|back end|python developer|node|golang|java developer|api|django|fastapi|software engineer)\b",
        "banned_title_regex": r"\b(trainer|annotation|coding tasks|frontend|front-end|react|ui/ux|data analyst|recruiter|sales)\b"
    },
    "fullstack": {
        "triggers": [r"full stack", r"fullstack", r"full-stack"],
        "valid_title_regex": r"\b(full stack|fullstack|full-stack|software engineer|web developer)\b",
        "banned_title_regex": r"\b(trainer|annotation|coding tasks|data analyst|recruiter|sales|marketing|support|hr)\b"
    },
    "devops_cloud": {
        "triggers": [r"devops", r"\bcloud\b", r"\bsre\b", r"\bkubernetes\b"],
        "valid_title_regex": r"\b(devops|cloud|sre|reliability|infrastructure|platform engineer|aws|kubernetes)\b",
        "banned_title_regex": r"\b(trainer|annotation|frontend|react|ui/ux|sales|marketing)\b"
    },
    "cybersecurity": {
        "triggers": [r"security", r"cyber", r"penetration", r"\bsoc\b", r"infosec"],
        "valid_title_regex": r"\b(security|cyber|cybersecurity|soc|penetration|pentest|infosec)\b",
        "banned_title_regex": r"\b(trainer|annotation|frontend|react|sales|marketing)\b"
    }
}

def detect_family(role_or_query: str, skills: list) -> str:
    combined = (role_or_query + " " + " ".join(skills[:8])).lower()
    for fam_key, fam_data in ROLE_RULES.items():
        if any(re.search(trig, combined) for trig in fam_data["triggers"]):
            return fam_key
    return "general"

def is_title_valid(title: str, family: str) -> bool:
    t_low = title.lower()
    # حظر عام لوظائف التدريب الوهمية وغير التقنية في جميع التخصصات
    global_ban = r"\b(trainer|annotation|annotator|rater|labeler|coding tasks|tutor|sales|recruiter|hr|customer support|accountant)\b"
    if re.search(global_ban, t_low):
        return False

    if family not in ROLE_RULES:
        return True

    rules = ROLE_RULES[family]
    if re.search(rules["banned_title_regex"], t_low):
        return False
    if re.search(rules["valid_title_regex"], t_low):
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

    def add_job_if_valid(title, comp, loc, raw_desc, url):
        if not title or not is_title_valid(title, family):
            return
        key = f"{title}_{comp}".lower()
        if key in seen_titles:
            return
        seen_titles.add(key)
        clean_desc = re.sub(r'<[^>]+>', ' ', raw_desc or "")
        clean_desc = re.sub(r'\s+', ' ', clean_desc).strip()
        jobs.append({
            "Title": title,
            "Company": comp or "Tech Company",
            "Location": loc or "Remote",
            "Description": clean_desc[:420] + "...",
            "Full_Text": (title + " " + clean_desc).lower(),
            "Apply_Link": url or "#"
        })

    # المصدر الأول: قنوات Remotive الكاملة (بدون search ضيق يضيع الوظائف)
    remotive_urls = [
        "https://remotive.com/api/remote-jobs?category=data&limit=100",
        "https://remotive.com/api/remote-jobs?category=software-dev&limit=100",
        f"https://remotive.com/api/remote-jobs?search={search_query}&limit=50"
    ]
    for url in remotive_urls:
        try:
            r = requests.get(url, timeout=6)
            if r.status_code == 200:
                for item in r.json().get("jobs", []):
                    add_job_if_valid(
                        item.get("title", ""),
                        item.get("company_name", ""),
                        item.get("candidate_required_location", "Remote"),
                        item.get("description", ""),
                        item.get("url", "#")
                    )
        except Exception:
            pass

    # المصدر الثاني: Arbeitnow Job Board API (مصدر مجاني غني بوظائف AI و Software)
    try:
        r2 = requests.get("https://www.arbeitnow.com/api/job-board-api", timeout=6)
        if r2.status_code == 200:
            for item in r2.json().get("data", []):
                tags_str = " ".join(item.get("tags", []))
                add_job_if_valid(
                    item.get("title", ""),
                    item.get("company_name", ""),
                    item.get("location", "Remote"),
                    item.get("description", "") + " " + tags_str,
                    item.get("url", "#")
                )
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

        if not is_title_valid(title_lower, family):
            continue

        job_skills = {s for s in VOCAB.keys() if s not in NOISY_SKILLS and re.search(skill_regex(s), desc_lower)}
        matched_all = sorted([s for s in job_skills if s in all_user_skills])
        missing = sorted(list(job_skills - all_user_skills))[:6]

        # استبعاد الوظائف التي لا تتقاطع مع مهارات المستخدم على الإطلاق (عند توفر مهارات)
        if user_skills and len(matched_all) == 0:
            continue

        # 1. حساب دقيق لنسبة المهارات (المقام لا يقل عن 5 مهارات لمنع 1/1 = 100%)
        denom = max(min(len(job_skills), 8), 5)
        skill_pct = int(min((len(matched_all) / denom) * 100, 96))
        
        # مكافأة إذا كان العنوان يحتوي على المسمى الصريح للتخصص (مثل Machine Learning أو AI Engineer)
        if re.search(r"\b(machine learning|ai engineer|data scientist|deep learning|computer vision|nlp)\b", title_lower):
            skill_pct = min(skill_pct + 15, 98)

        skill_pct = max(skill_pct, 45)

        # 2. حساب نسبة المستوى الوظيفي (Level_Pct)
        is_job_senior = any(w in title_lower for w in ["senior", "sr.", "sr ", "lead", "principal", "staff", "head", "director"])
        is_job_junior = any(w in title_lower for w in ["junior", "jr.", "jr ", "entry", "intern", "graduate", "associate"])

        u_lvl = user_level.lower()
        if "student" in u_lvl or "entry" in u_lvl:
            level_pct = 96 if is_job_junior else (60 if is_job_senior else 85)
        elif "experienced" in u_lvl or "mid" in u_lvl:
            level_pct = 88 if is_job_senior else (76 if is_job_junior else 94)
        else:
            level_pct = 94 if is_job_senior else 78

        # 3. حساب نسبة الخبرة (Exp_Pct)
        req_exp_matches = re.findall(r'(\d+)\+?\s*(?:years?|yrs?)', desc_lower)
        req_years = [int(x) for x in req_exp_matches if 1 <= int(x) <= 15]
        if req_years:
            job_req_exp = min(req_years)
            diff = float(user_exp) - job_req_exp
            exp_pct = 95 if diff >= 0 else int(max(92 - (abs(diff) * 9), 55))
        else:
            exp_pct = 88 if not is_job_senior else (68 if float(user_exp) < 3 else 92)

        # 4. الدرجة الكلية الموزونة
        match_score = int((skill_pct * 0.60) + (exp_pct * 0.20) + (level_pct * 0.20))
        match_score = min(max(match_score, 50), 98)

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

    ranked = sorted(ranked, key=lambda x: (x["Match_Score"], len(x["Matched_Skills"])), reverse=True)
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
    query = skills[0] if skills else "AI Engineer"
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
