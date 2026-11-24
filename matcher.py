import pandas as pd
from sklearn.metrics.pairwise import cosine_similarity
from cv_analyzer import load_models, clean_text

def calculate_experience_score(job_min_exp, user_exp):
    if job_min_exp is None or pd.isna(job_min_exp):
        return 0.5
    try:
        j_exp, u_exp = float(job_min_exp), float(user_exp)
    except (ValueError, TypeError):
        return 0.5
    if u_exp >= j_exp:
        return 1.0
    diff = j_exp - u_exp
    return float(max(0.0, min(1.0, 1.0 - (diff * 0.2))))

def calculate_level_score(job_level, user_level):
    if not job_level or pd.isna(job_level):
        return 0.5
    j_lvl, u_lvl = str(job_level).strip().lower(), str(user_level).strip().lower()
    if j_lvl == u_lvl:
        return 1.0
    order = ['student', 'entry level', 'experienced', 'manager', 'senior management']
    if j_lvl in order and u_lvl in order:
        dist = abs(order.index(j_lvl) - order.index(u_lvl))
        return 0.6 if dist == 1 else (0.3 if dist == 2 else 0.1)
    return 0.4

def calculate_skill_gap(job_skills_list, user_skills_set):
    job_set = set(job_skills_list)
    matched = sorted(list(job_set.intersection(user_skills_set)))
    missing = sorted(list(job_set.difference(user_skills_set)))
    return matched, missing

def calculate_match_score(cv_data, jobs_df):
    _, _, skills_vectorizer, _ = load_models()
    
    if not skills_vectorizer or jobs_df.empty:
        return []

    user_skills_set = set(cv_data.get('skills', []))
    user_skills_text = cv_data.get('skills_text', '') or cv_data.get('cleaned_text', '')

    user_vec = skills_vectorizer.transform([user_skills_text])
    jobs_df = jobs_df.copy()
    
    desc_col = 'Description' if 'Description' in jobs_df.columns else 'Title'
    jobs_df['Clean_Description'] = (
        jobs_df['Title'].astype(str) + " " + jobs_df[desc_col].astype(str)
    ).apply(clean_text)

    cand_skills_mat = skills_vectorizer.transform(jobs_df['Clean_Description'])
    jobs_df['Skill_Similarity'] = cosine_similarity(user_vec, cand_skills_mat)[0]
    
    exp_col = jobs_df['Experience_Level'] if 'Experience_Level' in jobs_df.columns else pd.Series([None]*len(jobs_df))
    lvl_col = jobs_df['Career_Level'] if 'Career_Level' in jobs_df.columns else pd.Series([None]*len(jobs_df))

    jobs_df['Exp_Score'] = exp_col.apply(lambda e: calculate_experience_score(e, cv_data.get('experience_level', 2.0)))
    jobs_df['Level_Score'] = lvl_col.apply(lambda l: calculate_level_score(l, cv_data.get('career_level', 'Entry Level')))

    jobs_df['Final_Score'] = (
        0.70 * jobs_df['Skill_Similarity'] +
        0.20 * jobs_df['Exp_Score'] +
        0.10 * jobs_df['Level_Score']
    )

   ranked_jobs = []
    top_jobs = jobs_df.sort_values('Final_Score', ascending=False)
    
    for _, row in top_jobs.iterrows():
        job_vec = skills_vectorizer.transform([row['Clean_Description']])
        job_skills_list = skills_vectorizer.inverse_transform(job_vec)[0].tolist()
        
        matched, missing = calculate_skill_gap(job_skills_list, user_skills_set)
        
        # --- التعديل هنا لنسبة واقعية ---
        total_job_skills = len(matched) + len(missing)
        
        # حساب نسبة المهارات الحقيقية بناءً على العدد
        if total_job_skills > 0:
            actual_skill_score = len(matched) / total_job_skills
        else:
            # لو الوظيفة مفهاش مهارات واضحة، بنعتمد على الـ Similarity القديمة بس بنقللها للنص عشان ماتبقاش وهمية
            actual_skill_score = float(row['Skill_Similarity']) * 0.5 

        # إعادة حساب السكور النهائي (70% مهارات حقيقية، 20% خبرة، 10% مستوى)
        real_final_score = (0.70 * actual_skill_score) + (0.20 * float(row['Exp_Score'])) + (0.10 * float(row['Level_Score']))
        
        job_dict = {k: (None if pd.isna(v) else v) for k, v in row.to_dict().items()}
        
        # شيلنا الحد الأقصى (99) وبقينا نعتمد على النسبة الواقعية
        job_dict["Match_Score"] = int(real_final_score * 100)
        job_dict["Skill_Pct"] = round(actual_skill_score * 100, 1)
        job_dict["Exp_Pct"] = round(min(float(row['Exp_Score']) * 100, 100), 1)
        job_dict["Level_Pct"] = round(min(float(row['Level_Score']) * 100, 100), 1)
        job_dict["Matched_Skills"] = matched
        job_dict["Missing_Skills"] = missing
        
        # فلتر إضافي: لو الوظيفة السكور بتاعها أقل من 15% مش هنضيفها عشان مانعرضش وظايف ملهاش علاقة خالص
        if job_dict["Match_Score"] >= 15:
            ranked_jobs.append(job_dict)

    # إعادة ترتيب الوظايف بناءً على السكور الواقعي الجديد
    ranked_jobs = sorted(ranked_jobs, key=lambda x: x["Match_Score"], reverse=True)

    return ranked_jobs
