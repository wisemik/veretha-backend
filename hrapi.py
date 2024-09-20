from fastapi import UploadFile, File, Form
from pdfminer.high_level import extract_text
import openai
import uvicorn
import json
from dotenv import load_dotenv
from fastapi.middleware.cors import CORSMiddleware
from fastapi import FastAPI
import os
from pydantic import BaseModel
import requests

app = FastAPI()
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
load_dotenv()

PROXYCURL_API_KEY = os.getenv('PROXYCURL_API_KEY')
OPENAI_API_KEY = os.getenv('OPENAI_API_KEY')
openai.api_key = OPENAI_API_KEY


class ScoreRequest(BaseModel):
    resume_text: str
    job_description: str


class LinkedInRequest(BaseModel):
    linkedin_url: str


@app.post("/extract-text")
async def extract_text_from_pdf(file: UploadFile = File(...)):
    if file.content_type == 'application/pdf':
        contents = await file.read()
        with open(f"{file.filename}", 'wb') as f:
            f.write(contents)
        try:
            text = extract_text(file.filename)
            os.remove(file.filename)
            return {"extracted_text": text}
        except Exception as e:
            return {"error": str(e)}
    else:
        return {"error": "Invalid file type. Please upload a PDF."}


def fetch_linkedin_profile(linkedin_url):
    api_endpoint = 'https://nubela.co/proxycurl/api/v2/linkedin'
    headers = {'Authorization': 'Bearer ' + PROXYCURL_API_KEY}
    params = {
        'linkedin_profile_url': linkedin_url,
        'use_cache': 'if-present',  # Use cache to reduce API cost
        'fallback_to_cache': 'on-error',  # Fallback to cache if there's an error
    }

    response = requests.get(api_endpoint, params=params, headers=headers)

    if response.status_code == 200:
        print(f"LinkedIn profile fetched successfully for URL: {linkedin_url}")
        return response.json()
    else:
        print(f"Failed to fetch LinkedIn profile: {response.status_code} - {response.text}")
        return {}


@app.post("/score-resume")
async def score_resume(request: ScoreRequest):
    print(f"Received resume text: {request.resume_text}")
    print(f"Received job description: {request.job_description}")
    messages = generate_prompt_messages(request.resume_text, request.job_description)

    try:
        response = openai.chat.completions.create(model="gpt-4o-mini",
                                                  messages=messages)
        content = response.choices[0].message.content
        print(f"Received response from OpenAI: {content}")
        result = json.loads(content)

        score = result.get("score", 0)
        description = result.get("description", "No description provided.")
        details = result.get("details", "No details provided.")
        print(f"Extracted score: {score}, description: {description}, improvements: {details}")
        return {"score_result": score, "description": description, "improvements": details}
    except Exception as e:
        return {"error": str(e)}


@app.post("/extract-linkedin")
async def extract_linkedin(linkedin_request: LinkedInRequest):
    linkedin_url = linkedin_request.linkedin_url
    print(f"Received LinkedIn URL: {linkedin_url}")
    profile_data = fetch_linkedin_profile(linkedin_url)
    print(f"Profile data: {profile_data}")

    return {"linkedin_data": profile_data}


def generate_prompt_messages(resume_text, job_description):
    prompt = f"""
                   You are a career consultant helping candidates assess how well their resume matches a specific job vacancy. 
                   You will be provided with the candidate's resume and the job description. 
                   Your task is to provide an objective evaluation of how well the resume fits the job requirements, 
                   give feedback, and offer suggestions on how the resume can be improved for a better match.

                   Please provide the result in JSON format (only JSON!! without any additional symbols), containing the following fields:
                   - "score": a string  (0-100) representing the match between the resume and the job description, where 0 - no match at all and 100 means a perfect match.
                   - "description": a string containing feedback on how well the resume fits the job requirements (in English).
                   - "details": a string containing suggestions for improving the resume to better match the job description. 

                   Evaluation criteria:
                   1) Experience requirements: Does your experience meet the job's requirements?
                   2) Skills: Do your skills match the required competencies?
                   3) Education: Do you have relevant education?
                   4) Location: Does the job's location match your preferences?
                   5) Other signals: How well do you fit into the company culture?

                   Candidate's resume: {resume_text}
                   Job description: {job_description}

                   The output must be in JSON!! without any additional symbols. 
                   Only the dictionary itself.
               """
    messages = [
        {
            "role": "system",
            "content": "You are a career consultant helping candidates improve their resumes. "
                       "Always respond in JSON format. Output should be JSON only!!"
                       "NO additional symbols. Only the dictionary itself."
        },
        {"role": "user", "content": prompt}
    ]

    return messages


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)
