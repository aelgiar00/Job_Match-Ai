import os
import requests
from functools import lru_cache

@lru_cache(maxsize=64)
def fetch_live_jobs(job_role: str, country_code: str = "eg"):
    url = "https://jsearch.p.rapidapi.com/search-v2"
    query_text = f"{job_role} in {country_code}"
    
    querystring = {
        "query": query_text,
        "num_pages": "1",
        "country": country_code,
        "date_posted": "all"
    }
    
    api_key = os.getenv("RAPIDAPI_KEY", "56ac03e744msh7331c6ffc78992fp1b7d0ejsnc411b61b39b2")
    headers = {
        "x-rapidapi-key": api_key,
        "x-rapidapi-host": "jsearch.p.rapidapi.com"
    }
    
    try:
        response = requests.get(url, headers=headers, params=querystring, timeout=15)
        response.raise_for_status() 
        result = response.json()
        
        data_field = result.get('data', [])
        jobs_data = data_field.get('jobs', []) if isinstance(data_field, dict) else data_field
            
        cleaned_jobs = []
        for job in jobs_data:
            req_exp = job.get('job_required_experience') or {}
            exp_months = req_exp.get('required_experience_in_months')
            
            job_info = {
                "Title": job.get('job_title', 'N/A'),
                "Company": job.get('employer_name', 'N/A'),
                "Location": job.get('job_location') or job.get('job_city') or country_code.upper(),
                "Description": job.get('job_description', 'No description available.'),
                "Apply_Link": job.get('job_apply_link', '#'),
                "Date": job.get('job_posted_at_datetime_utc', ''),
                "Experience_Level": (exp_months / 12.0) if exp_months else None,
                "Career_Level": "Experienced",
                "Source": "Live API"
            }
            cleaned_jobs.append(job_info)
            
        return cleaned_jobs

    except Exception as e:
        print(f"An error occurred while fetching data from API: {e}")
        return []