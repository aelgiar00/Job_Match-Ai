import requests
import streamlit as st

@st.cache_data(ttl=3600, show_spinner=False)
def fetch_live_jobs(job_role, country_code="eg"):
    url = "https://jsearch.p.rapidapi.com/search-v2"
    query_text = f"{job_role} in {country_code}"
    
    querystring = {
        "query": query_text,
        "num_pages": "1",
        "country": country_code,
        "date_posted": "all"
    }
    
    headers = {
        "x-rapidapi-key": "56ac03e744msh7331c6ffc78992fp1b7d0ejsnc411b61b39b2", # Add to secrets.toml later
        "x-rapidapi-host": "jsearch.p.rapidapi.com"
    }
    
    try:
        response = requests.get(url, headers=headers, params=querystring)
        response.raise_for_status() 
        result = response.json()
        
        data_field = result.get('data', [])
        
        if isinstance(data_field, dict):
            jobs_data = data_field.get('jobs', [])
        else:
            jobs_data = data_field 
            
        cleaned_jobs = []
        
        for job in jobs_data:
            job_info = {
                "Title": job.get('job_title', 'N/A'),
                "Company": job.get('employer_name', 'N/A'),
                "Location": job.get('job_location', 'N/A'),
                "Description": job.get('job_description', 'No description available.'),
                "Apply_Link": job.get('job_apply_link', '#'),
                "Experience_Level": job.get('job_required_experience', {}).get('required_experience_in_months', 0) / 12 if job.get('job_required_experience') else None,
                "Career_Level": "Experienced" # Default mapping
            }
            cleaned_jobs.append(job_info)
            
        return cleaned_jobs

    except Exception as e:
        print(f"An error occurred while fetching data from API: {e}")
        return []
