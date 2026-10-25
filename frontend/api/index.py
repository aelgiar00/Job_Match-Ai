import os, io, re, json
import urllib.parse
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

COUNTRY_MAP = {
    "eg": {
        "name": "Egypt",
        "cities": ["Cairo, Egypt", "Smart Village, Giza, Egypt", "New Cairo, Egypt", "Maadi, Cairo, Egypt", "Alexandria, Egypt"],
        "valid_loc_keywords": ["egypt", "cairo", "giza", "alexandria", "mena", "emea", "middle east", "worldwide", "anywhere", "global"],
        "banned_loc_keywords": ["germany only", "berlin only", "london only", "uk only", "usa only", "us only", "canada only", "australia only"]
    },
    "sa": {
        "name": "Saudi Arabia",
        "cities": ["Riyadh, Saudi Arabia", "Jeddah, Saudi Arabia", "Dammam, Saudi Arabia"],
        "valid_loc_keywords": ["saudi", "riyadh", "jeddah", "ksa", "mena", "gcc", "middle east", "worldwide", "anywhere"],
        "banned_loc_keywords": ["germany", "london", "uk", "usa", "canada", "europe"]
    },
    "ae": {
        "name": "UAE",
        "cities": ["Dubai, UAE", "Abu Dhabi, UAE", "Dubai Internet City, UAE"],
        "valid_loc_keywords": ["uae", "dubai", "abu dhabi", "emirates", "mena", "gcc", "middle east", "worldwide", "anywhere"],
        "banned_loc_keywords": ["germany", "london", "uk", "usa", "canada", "europe"]
    },
    "us": {
        "name": "United States",
        "cities": ["San Francisco, CA (Remote)", "New York, NY", "Austin, TX", "USA (Remote)"],
        "valid_loc_keywords": ["usa", "united states", "us", "north america", "worldwide", "anywhere", "remote"],
        "banned_loc_keywords": ["germany only", "london only", "uk only"]
    }
}

ROLE_RULES = {
    "ai_data": {
        "triggers": [r"\bai\b", r"machine learning", r"\bml\b", r"data scien", r"deep learning", r"\bnlp\b", r"computer vision", r"artificial intelligence", r"data analy"],
        "valid_title_regex": r"\b(ai|ml|machine learning|data scientist|data science|data analyst|data engineer|deep learning|nlp|computer vision|artificial intelligence|llm|genai|mlops|python)\b",
        "banned_title_regex": r"\b(trainer|annotation|annotator|rater|labeler|coding tasks|prompt writer|tutor|frontend|front-end|react|angular|vue|rails|ruby|php|laravel|wordpress|ios|android|flutter|full stack|fullstack|full-stack|back-end|backend|ui/ux|sales|marketing|recruiter|hr|support|accountant|\.net|c#)\b",
        "role_templates": [
            ("AI Engineer", ["python", "machine learning", "deep learning", "pytorch", "tensorflow", "nlp", "fastapi", "git"]),
            ("Machine Learning Engineer", ["python", "scikit-learn", "machine learning", "pandas", "numpy", "tensorflow", "sql", "git"]),
            ("Computer Vision & AI Developer", ["python", "opencv", "computer vision", "deep learning", "cnn", "tensorflow", "pytorch", "numpy"]),
            ("NLP & Generative AI Engineer", ["python", "nlp", "deep learning", "machine learning", "pytorch", "tensorflow", "git", "fastapi"]),
            ("Data Scientist & ML Specialist", ["python", "machine learning", "data analysis", "pandas", "scikit-learn", "sql", "matplotlib", "seaborn"]),
            ("AI & Data Analytics Engineer", ["python", "sql", "data analysis", "pandas", "machine learning", "numpy", "probability", "git"])
        ]
    },
    "frontend": {
        "triggers": [r"frontend", r"front-end", r"\breact\b", r"\bangular\b", r"\bvue\b"],
        "valid_title_regex": r"\b(frontend|front-end|front end|react|angular|vue|ui developer|web developer|javascript|typescript)\b",
        "banned_title_regex": r"\b(trainer|annotation|backend|back-end|data scientist|machine learning|devops|security|ios|android|sales|hr)\b",
        "role_templates": [
            ("Frontend Developer (React.js)", ["react", "typescript", "javascript", "html", "css", "tailwind css", "git"]),
            ("UI / Frontend Software Engineer", ["javascript", "react", "next.js", "css", "html", "git", "rest api"])
        ]
    },
    "backend": {
        "triggers": [r"backend", r"back-end", r"\bnode\b", r"\bdjango\b", r"\bfastapi\b", r"\bspring\b", r"\blaravel\b"],
        "valid_title_regex": r"\b(backend|back-end|back end|python developer|node|golang|java developer|api|django|fastapi|software engineer)\b",
        "banned_title_regex": r"\b(trainer|annotation|coding tasks|frontend|front-end|react|ui/ux|data analyst|recruiter|sales)\b",
        "role_templates": [
            ("Backend Engineer (Python / FastAPI)", ["python", "fastapi", "sql", "postgresql", "docker", "git", "rest api"]),
            ("Software Backend Developer", ["python", "django", "sql", "git", "linux", "api"])
        ]
    },
    "fullstack": {
        "triggers": [r"full stack", r"fullstack", r"full-stack"],
        "valid_title_regex": r"\b(full stack|fullstack|full-stack|software engineer|web developer)\b",
        "banned_title_regex": r"\b(trainer|annotation|coding tasks|data analyst|recruiter|sales|marketing|support|hr)\b",
        "role_templates": [
            ("Full Stack Software Engineer", ["react", "python", "fastapi", "typescript", "sql", "git", "tailwind css"]),
            ("Full-Stack Web Developer", ["javascript", "react", "node.js", "sql", "mongodb", "git"])
        ]
    },
    "devops_cloud": {
        "triggers": [r"devops", r"\bcloud\b", r"\bsre\b", r"\bkubernetes\b"],
        "valid_title_regex": r"\b(devops|cloud|sre|reliability|infrastructure|platform engineer|aws|kubernetes)\b",
        "banned_title_regex": r"\b(trainer|annotation|frontend|react|ui/ux|sales|marketing)\b",
        "role_templates": [
            ("Cloud & DevOps Engineer", ["aws", "docker", "kubernetes", "linux", "ci/cd", "terraform", "git"])
        ]
    },
    "cybersecurity": {
        "triggers": [r"security", r"cyber", r"penetration", r"\bsoc\b", r"infosec"],
        "valid_title_regex": r"\b(security|cyber|cybersecurity|soc|penetration|pentest|infosec)\b",
        "banned_title_regex": r"\b(trainer|annotation|frontend|react|sales|marketing)\b",
        "role_templates": [
            ("Cybersecurity & SOC Analyst", ["network security", "linux", "siem", "penetration testing", "python"])
        ]
    }
}

SENIOR_TITLE_REGEX = r"\b(senior|sr\.?|lead|principal|staff|head|director|manager|vp|chief|architect)\b"
JUNIOR_TITLE_REGEX = r"\b(junior|jr\.?|entry|entry-level|intern|internship|graduate|fresh|associate|trainee)\b"

def detect_family(role_or_query: str, skills: list) -> str:
    combined = (role_or_query + " " + " ".join(skills[:10])).lower()
    for fam_key, fam_data in ROLE_RULES.items():
        if any(re.search(trig, combined) for trig in fam_data["triggers"]):
            return fam_key
    return "ai_data"

def extract_experience_and_level(raw_text: str):
    t_low = raw_text.lower()
    is_student_or_fresh = any(w in t_low for w in ["student", "undergraduate", "level 3", "level 4", "fresh graduate", "intern ", "internship", "trainee"])
    
    exp_matches = re.findall(r'(\d+(?:\.\d+)?)\+?\s*(?:years?|yrs?)\s+(?:of\s+)?(?:experience|exp)', t_low)
    if exp_matches:
        exp_years = float(max([float(x) for x in exp_matches if float(x) <= 20], default=1.5))
    else:
        exp_years = 1.0 if is_student_or_fresh else 1.5

    if exp_years <= 2.0 or is_student_or_fresh:
        level = "Junior / Entry Level"
    elif exp_years <= 4.5:
        level = "Mid-Level"
    else:
        level = "Senior"

    return exp_years, level

def is_seniority_compatible(job_title: str, job_desc: str, user_level: str, user_exp: float) -> bool:
    """نظام مرن يتوافق مع مستوى المستخدم الحقيقي (Junior يرى Junior/Mid - Senior يرى Senior/Mid)"""
    t_low = job_title.lower()
    u_lvl = user_level.lower()
    
    is_job_senior = bool(re.search(SENIOR_TITLE_REGEX, t_low))
    is_job_junior = bool(re.search(JUNIOR_TITLE_REGEX, t_low))
    
    # 1. إذا كان المستخدم Junior أو Student: نستبعد فقط الوظائف القيادية الكبرى (Lead, Principal, Director)
    if any(k in u_lvl for k in ["student", "entry", "junior", "fresh"]) or float(user_exp) <= 2.5:
        if any(w in t_low for w in ["lead", "principal", "staff", "head", "director", "manager", "architect"]):
            return False
            
    # 2. إذا كان المستخدم Senior: نستبعد وظائف التدريب والـ Intern والـ Junior البحتة
    elif "senior" in u_lvl or float(user_exp) >= 5.0:
        if is_job_junior or re.search(r"\b(intern|internship|trainee|fresh graduate)\b", t_low):
            return False

    return True

def is_location_compatible(job_loc: str, country_code: str) -> bool:
    loc_low = (job_loc or "").lower().strip()
    c_code = (country_code or "eg").lower().strip()
    
    c_info = COUNTRY_MAP.get(c_code, {
        "name": c_code.upper(),
        "valid_loc_keywords": [c_code, "worldwide", "anywhere", "global"],
        "banned_loc_keywords": ["usa only", "uk only", "germany only", "berlin only", "london only"]
    })

    if any(b in loc_low for b in c_info["banned_loc_keywords"]):
        return False

    if any(v in loc_low for v in c_info["valid_loc_keywords"]):
        return True

    if loc_low in ["remote", "anywhere", "worldwide", ""]:
        return True

    return False

def is_title_valid(title: str, family: str) -> bool:
    t_low = title.lower()
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

def generate_regional_targeted_jobs(family: str, user_skills: list, user_level: str, user_exp: float, country_code: str = "eg"):
    c_code = (country_code or "eg").lower().strip()
    c_info = COUNTRY_MAP.get(c_code, {
        "name": c_code.upper(),
        "cities": [f"{c_code.upper()} (Remote)", f"Capital, {c_code.upper()}"]
    })
    
    u_lvl = user_level.lower()
    if any(k in u_lvl for k in ["student", "entry", "junior", "fresh"]) or float(user_exp) <= 2.5:
        prefixes = ["Junior", "Associate", "Junior", ""]
        exp_text = "0 to 2 years of hands-on experience."
    elif "mid" in u_lvl or float(user_exp) <= 4.5:
        prefixes = ["Mid-Level", "", "Software"]
        exp_text = "2 to 4 years of practical industry experience."
    else:
        prefixes = ["Senior", "Lead", "Senior"]
        exp_text = "5+ years of proven track record."

    companies_by_country = {
        "eg": ["Valeo Egypt", "Instabug", "Vodafone Intelligent Solutions", "Fawry", "Swvl", "Paymob", "Robusta Studio", "Breadfast", "Synapse Analytics", "Intella"],
        "sa": ["STC Solutions", "Mozn", "SDAIA", "Lean Business Services", "Tamara"],
        "ae": ["Careem", "Noon", "Talabat", "G42", "Astra Tech"]
    }
    comp_list = companies_by_country.get(c_code, ["Regional Tech Hub", "MENA AI Labs", "Global Tech Solutions"])

    rules = ROLE_RULES.get(family, ROLE_RULES["ai_data"])
    templates = rules.get("role_templates", ROLE_RULES["ai_data"]["role_templates"])

    regional_jobs = []
    user_top_skills = [s.lower() for s in user_skills[:6]] if user_skills else []

    for idx, (base_title, core_skills) in enumerate(templates):
        prefix = prefixes[idx % len(prefixes)]
        full_title = f"{prefix} {base_title}".strip()
        company = comp_list[idx % len(comp_list)].strip()
        city = c_info["cities"][idx % len(c_info["cities"])]

        combined_skills = list(dict.fromkeys(user_top_skills[:4] + core_skills))
        skills_str = ", ".join([s.title() for s in combined_skills[:7]])

        desc = (
            f"We are hiring a {full_title} based in {city} to join our engineering team at {company}. "
            f"Requirements: {exp_text} "
            f"Strong proficiency in {skills_str}. "
            f"You will design, develop, and deploy scalable solutions tailored for the {c_info['name']} market."
        )

        q_encoded = urllib.parse.quote(full_title)
        loc_encoded = urllib.parse.quote(c_info["name"])
        apply_url = f"https://www.linkedin.com/jobs/search/?keywords={q_encoded}&location={loc_encoded}"

        regional_jobs.append({
            "Title": full_title,
            "Company": company,
            "Location": city,
            "Description": desc,
            "Full_Text": (full_title + " " + desc + " " + " ".join(combined_skills)).lower(),
            "Apply_Link": apply_url
        })

    return regional_jobs

def fetch_targeted_jobs(search_query: str, top_skills: list, country: str = "eg", strict_family: str = None, user_level: str = "Junior / Entry Level", user_exp: float = 1.5):
    jobs = []
    seen_titles = set()
    family = strict_family or detect_family(search_query, top_skills)
    c_code = (country or "eg").lower().strip()
    c_name = COUNTRY_MAP.get(c_code, {}).get("name", c_code.upper())

    def add_job_if_valid(title, comp, loc, raw_desc, url):
        if not title or not is_title_valid(title, family):
            return
        if not is_location_compatible(loc, c_code):
            return
        clean_desc = re.sub(r'<[^>]+>', ' ', raw_desc or "")
        clean_desc = re.sub(r'\s+', ' ', clean_desc).strip()
        if not is_seniority_compatible(title, clean_desc, user_level, user_exp):
            return

        key = f"{title}_{comp}".lower()
        if key in seen_titles:
            return
        seen_titles.add(key)

        display_loc = f"{c_name} / Remote ({loc})" if loc.lower() in ["worldwide", "anywhere", "remote"] else loc
        jobs.append({
            "Title": title,
            "Company": comp or "Tech Company",
            "Location": display_loc,
            "Description": clean_desc[:420] + "...",
            "Full_Text": (title + " " + clean_desc).lower(),
            "Apply_Link": url or "#"
        })

    remotive_urls = [
        "https://remotive.com/api/remote-jobs?category=data&limit=100",
        "https://remotive.com/api/remote-jobs?category=software-dev&limit=100"
    ]
    for url in remotive_urls:
        try:
            r = requests.get(url, timeout=5)
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

    regional_jobs = generate_regional_targeted_jobs(family, top_skills, user_level, user_exp, c_code)
    for r_job in regional_jobs:
        key = f"{r_job['Title']}_{r_job['Company']}".lower()
        if key not in seen_titles:
            seen_titles.add(key)
            jobs.append(r_job)

    return jobs

def rank_and_filter_jobs(jobs, user_skills, user_exp, user_level, user_role="", country_code="eg"):
    if not jobs:
        return []

    all_user_skills = {s.lower().strip() for s in user_skills}
    family = detect_family(user_role, user_skills)
    c_code = (country_code or "eg").lower().strip()
    c_name = COUNTRY_MAP.get(c_code, {}).get("name", "Egypt").lower()
    ranked = []

    for job in jobs:
        title_lower = job["Title"].lower()
        desc_lower = job.get("Full_Text", (title_lower + " " + job["Description"]).lower())

        if not is_title_valid(title_lower, family):
            continue
        if not is_seniority_compatible(job["Title"], desc_lower, user_level, user_exp):
            continue

        job_skills = {s for s in VOCAB.keys() if s not in NOISY_SKILLS and re.search(skill_regex(s), desc_lower)}
        matched_all = sorted([s for s in job_skills if s in all_user_skills])
        missing = sorted(list(job_skills - all_user_skills))[:6]

        if user_skills and len(matched_all) == 0:
            continue

        denom = max(min(len(job_skills), 7), 4)
        skill_pct = int(min((len(matched_all) / denom) * 100, 96))
        if re.search(r"\b(machine learning|ai|data scientist|deep learning|computer vision|nlp)\b", title_lower):
            skill_pct = min(skill_pct + 10, 98)
        skill_pct = max(skill_pct, 55)

        is_job_junior = bool(re.search(JUNIOR_TITLE_REGEX, title_lower))
        is_job_senior = bool(re.search(SENIOR_TITLE_REGEX, title_lower))
        u_lvl = user_level.lower()

        if any(k in u_lvl for k in ["student", "entry", "junior"]):
            level_pct = 96 if is_job_junior else 85
        elif "mid" in u_lvl or "experienced" in u_lvl:
            level_pct = 94 if not (is_job_junior or is_job_senior) else 88
        else:
            level_pct = 96 if is_job_senior else 75

        exp_pct = 94 if abs(float(user_exp) - 1.5) <= 1.5 else 88
        loc_bonus = 4 if c_name in job.get("Location", "").lower() else 0

        match_score = int((skill_pct * 0.60) + (exp_pct * 0.20) + (level_pct * 0.20)) + loc_bonus
        match_score = min(max(match_score, 60), 98)

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
    exp_years, level = extract_experience_and_level(raw_text)

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
    level = payload.get("career_level", "Junior / Entry Level")
    country = payload.get("country_code", "eg")

    family = detect_family(role, skills)
    jobs = fetch_targeted_jobs(role, skills, country, strict_family=family, user_level=level, user_exp=exp)
    return {"jobs": rank_and_filter_jobs(jobs, skills, exp, level, role, country)}

@app.post("/api/manual-recommendations")
async def manual_recs(payload: dict):
    skills_str = payload.get("skills", "")
    skills = [s.strip().lower() for s in re.split(r'[,;]', skills_str) if s.strip()]
    exp = payload.get("experience_years", 1.5)
    level = payload.get("career_level", "Junior / Entry Level")
    country = payload.get("country_code", "eg")

    family = detect_family(skills_str, skills)
    query = skills[0] if skills else "AI Engineer"
    jobs = fetch_targeted_jobs(query, skills, country, strict_family=family, user_level=level, user_exp=exp)
    return {"jobs": rank_and_filter_jobs(jobs, skills, exp, level, skills_str, country)}

@app.get("/api/live-jobs")
async def live_jobs(query: str = "AI Engineer", country: str = "eg"):
    family = detect_family(query, [query])
    jobs = fetch_targeted_jobs(query, [query], country, strict_family=family, user_level="Junior / Entry Level", user_exp=1.5)
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
