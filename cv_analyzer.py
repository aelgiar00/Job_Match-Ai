import re
import joblib
import numpy as np
import streamlit as st
from pypdf import PdfReader
import docx

@st.cache_resource
def load_models():
    try:
        # قراءة الموديلات من مجلد artifacts_v5 الذي قمت بتسميته
        clf = joblib.load('artifacts_v5/model.pkl')
        mlb = joblib.load('artifacts_v5/label_encoder.pkl')
        skills_vectorizer = joblib.load('artifacts_v5/skills_vectorizer.pkl')
        
        # الموديل الأحدث لا يستخدم text_vectorizer لذلك نمرره كـ None
        text_vectorizer = None 
        
        return clf, mlb, skills_vectorizer, text_vectorizer
    except FileNotFoundError as e:
        st.error(f"Error loading models: {e} - تأكد أن ملفات الـ .pkl موجودة مباشرة داخل فولدر artifacts_v5")
        return None, None, None, None

@st.cache_resource
def load_aliases():
    try:
        # قراءة قاموس المترادفات لتنظيف المهارات
        return joblib.load('artifacts_v5/skill_aliases.pkl')
    except Exception:
        return {}

def extract_text_from_file(uploaded_file):
    """استخراج النص من ملفات السيرة الذاتية (PDF, DOCX, TXT)"""
    text = ""
    file_name = uploaded_file.name.lower()
    try:
        if file_name.endswith(".pdf"):
            reader = PdfReader(uploaded_file)
            for page in reader.pages:
                page_text = page.extract_text()
                if page_text:
                    text += page_text + "\n"
        elif file_name.endswith(".docx"):
            doc = docx.Document(uploaded_file)
            for para in doc.paragraphs:
                text += para.text + "\n"
        elif file_name.endswith(".txt"):
            text = uploaded_file.read().decode("utf-8", errors="ignore")
    except Exception as e:
        st.error(f"Error reading file: {e}")
    return text

def clean_text(text):
    """تنظيف النص وتوحيد المصطلحات التقنية"""
    if not text:
        return ""
    text = str(text).lower()
    
    # استبدال المترادفات بالاسم القياسي للمهارة (مثل pyhton إلى python)
    aliases = load_aliases()
    for alias, canonical in aliases.items():
        # استخدام regex لضمان استبدال الكلمة بالكامل فقط
        pattern = r'(?<!\w)' + re.escape(alias) + r'(?!\w)'
        text = re.sub(pattern, canonical, text)
    
    # الحفاظ على الحروف والأرقام والرموز الهامة في التكنولوجيا (+ # . - /)
    text = re.sub(r'[^a-zA-Z0-9+#.\-/\s]', ' ', text)
    # إزالة المسافات الزائدة
    text = re.sub(r'\s+', ' ', text).strip()
    return text

def estimate_experience(text):
    """توقع عدد سنوات الخبرة من النص"""
    text_low = text.lower()
    # البحث عن أنماط مثل "5 years of experience" أو "3+ yrs"
    matches = re.findall(r'(\d+)\+?\s*(?:years?|yrs?)\s*(?:of\s+)?(?:experience)?', text_low)
    if matches:
        years = [int(m) for m in matches if int(m) <= 25]
        if years:
            return float(max(years))
            
    # إذا لم يجد أرقام، يخمن بناءً على الكلمات المفتاحية
    if "senior" in text_low or "lead" in text_low or "manager" in text_low:
        return 5.0
    elif "junior" in text_low or "entry" in text_low or "intern" in text_low:
        return 1.0
    return 2.0

def estimate_career_level(exp_years):
    """تحديد المستوى الوظيفي بناءً على سنوات الخبرة"""
    if exp_years < 1:
        return "Student"
    elif exp_years <= 2.5:
        return "Entry Level"
    elif exp_years <= 6:
        return "Experienced"
    else:
        return "Manager"

def analyze_cv(uploaded_file):
    """الدالة الرئيسية لتحليل السيرة الذاتية وإرجاع النتائج"""
    raw_text = extract_text_from_file(uploaded_file)
    cleaned_text = clean_text(raw_text)
    
    clf, mlb, skills_vectorizer, _ = load_models()
    if not clf or not mlb or not skills_vectorizer:
        return None

    # 1. استخراج المهارات التقنية النظيفة فقط باستخدام الـ Whitelist Vectorizer
    vec = skills_vectorizer.transform([cleaned_text])
    extracted_skills = sorted(skills_vectorizer.inverse_transform(vec)[0].tolist())
    skills_text = " ; ".join(extracted_skills)

    # 2. توقع المجال الوظيفي (Top Domain) بناءً على المهارات المستخرجة
    # نستخدم المهارات المستخرجة للتوقع، وإذا لم يجد مهارات يستخدم النص المنظف كاحتياطي
    vec_for_pred = skills_vectorizer.transform([skills_text if skills_text else cleaned_text])
    
    if hasattr(clf, "decision_function"):
        scores = clf.decision_function(vec_for_pred)[0]
    else:
        scores = clf.predict_proba(vec_for_pred)[0]
    
    # اختيار أعلى مجال وظيفي كنسبة مطابقة
    top_role = str(mlb.classes_[int(np.argmax(scores))])
    
    # 3. تقدير الخبرة
    exp_years = estimate_experience(raw_text)
    career_level = estimate_career_level(exp_years)

    return {
        "raw_text": raw_text,
        "cleaned_text": cleaned_text,
        "skills": extracted_skills,
        "skills_text": skills_text,
        "role": top_role,
        "experience_level": exp_years,
        "career_level": career_level
    }