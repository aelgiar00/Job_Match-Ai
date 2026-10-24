import sys
import types
import re
import io
import joblib
import numpy as np
from functools import lru_cache
from pypdf import PdfReader
import docx
import sklearn.linear_model
import sklearn.linear_model._sgd_fast as sgd_fast

# --- حل جذري لمشكلة _sgd_fast.Log في Python 3.13 ---
class DummyLog:
    def __init__(self, *args, **kwargs):
        pass
    def __setstate__(self, state):
        pass
    def __call__(self, *args, **kwargs):
        return 0.0

# ترقيع الموديول في الذاكرة قبل التحميل
proxy_mod = types.ModuleType('sklearn.linear_model._sgd_fast')
for attr in dir(sgd_fast):
    setattr(proxy_mod, attr, getattr(sgd_fast, attr))
proxy_mod.Log = DummyLog
sys.modules['sklearn.linear_model._sgd_fast'] = proxy_mod
setattr(sklearn.linear_model, '_sgd_fast', proxy_mod)
# ----------------------------------------------------

@lru_cache(maxsize=1)
def load_models():
    try:
        clf = joblib.load('artifacts_v5/model.pkl')
        mlb = joblib.load('artifacts_v5/label_encoder.pkl')
        skills_vectorizer = joblib.load('artifacts_v5/skills_vectorizer.pkl')
        text_vectorizer = None
        return clf, mlb, skills_vectorizer, text_vectorizer
    except FileNotFoundError as e:
        print(f"Error loading models: {e} - تأكد أن فولدر artifacts_v5 موجود بجانب الملفات")
        return None, None, None, None

@lru_cache(maxsize=1)
def load_aliases():
    try:
        return joblib.load('artifacts_v5/skill_aliases.pkl')
    except Exception:
        return {}

def extract_text_from_bytes(file_bytes: bytes, filename: str) -> str:
    """استخراج النص من الـ Bytes المرفوعة عبر FastAPI"""
    text = ""
    file_name = filename.lower()
    file_stream = io.BytesIO(file_bytes)
    
    try:
        if file_name.endswith(".pdf"):
            reader = PdfReader(file_stream)
            for page in reader.pages:
                page_text = page.extract_text()
                if page_text:
                    text += page_text + "\n"
        elif file_name.endswith(".docx"):
            doc = docx.Document(file_stream)
            for para in doc.paragraphs:
                text += para.text + "\n"
        elif file_name.endswith(".txt"):
            text = file_bytes.decode("utf-8", errors="ignore")
    except Exception as e:
        print(f"Error reading file: {e}")
    return text

def extract_contact_info(text: str):
    email_match = re.search(r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}', text)
    phone_match = re.search(r'(\+?\d{1,3}[\s-]?)?\(?\d{2,4}\)?[\s-]?\d{3,4}[\s-]?\d{3,4}', text)
    return {
        "email": email_match.group(0) if email_match else "Not Found",
        "phone": phone_match.group(0) if phone_match else "Not Found"
    }

def clean_text(text: str) -> str:
    if not text:
        return ""
    text = str(text).lower()
    
    aliases = load_aliases()
    for alias, canonical in aliases.items():
        pattern = r'(?<!\w)' + re.escape(alias) + r'(?!\w)'
        text = re.sub(pattern, canonical, text)
    
    text = re.sub(r'[^a-zA-Z0-9+#.\-/\s]', ' ', text)
    text = re.sub(r'\s+', ' ', text).strip()
    return text

def estimate_experience(text: str) -> float:
    text_low = text.lower()
    matches = re.findall(r'(\d+)\+?\s*(?:years?|yrs?)\s*(?:of\s+)?(?:experience)?', text_low)
    if matches:
        years = [int(m) for m in matches if int(m) <= 25]
        if years:
            return float(max(years))
            
    if "senior" in text_low or "lead" in text_low or "manager" in text_low:
        return 5.0
    elif "junior" in text_low or "entry" in text_low or "intern" in text_low:
        return 1.0
    return 2.0

def estimate_career_level(exp_years: float) -> str:
    if exp_years < 1:
        return "Student"
    elif exp_years <= 2.5:
        return "Entry Level"
    elif exp_years <= 6:
        return "Experienced"
    else:
        return "Manager"

def analyze_cv_bytes(file_bytes: bytes, filename: str):
    raw_text = extract_text_from_bytes(file_bytes, filename)
    cleaned_text = clean_text(raw_text)
    contact_info = extract_contact_info(raw_text)
    
    clf, mlb, skills_vectorizer, _ = load_models()
    if clf is None or mlb is None or skills_vectorizer is None:
        return None

    vec = skills_vectorizer.transform([cleaned_text])
    extracted_skills = sorted(skills_vectorizer.inverse_transform(vec)[0].tolist())
    skills_text = " ; ".join(extracted_skills)

    vec_for_pred = skills_vectorizer.transform([skills_text if skills_text else cleaned_text])
    
    try:
        if hasattr(clf, "decision_function"):
            scores = clf.decision_function(vec_for_pred)[0]
        else:
            scores = clf.predict_proba(vec_for_pred)[0]
    except Exception:
        # Fallback باستخدام الأوزان المباشرة (coef_) في حال اعترضت دالة الـ loss في Python 3.13
        scores = np.dot(vec_for_pred.toarray(), clf.coef_.T)[0] + clf.intercept_
    
    top_role = str(mlb.classes_[int(np.argmax(scores))])
    exp_years = estimate_experience(raw_text)
    career_level = estimate_career_level(exp_years)

    return {
        "raw_text": raw_text,
        "cleaned_text": cleaned_text,
        "skills": extracted_skills,
        "skills_text": skills_text,
        "role": top_role,
        "experience_level": exp_years,
        "career_level": career_level,
        "contact_info": contact_info
    }