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

app = FastAPI()
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
load_dotenv()

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
            return {"extracted_text": text}
        except Exception as e:
            return {"error": str(e)}
    else:
        return {"error": "Invalid file type. Please upload a PDF."}


@app.post("/score-resume")
async def score_resume(request: ScoreRequest):
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
        print(f"Extracted score: {score}, description: {description}, details: {details}")
        return {"score_result": score, "description": description, "details": details}
    except Exception as e:
        return {"error": str(e)}


@app.post("/extract-linkedin")
async def extract_linkedin(linkedin_url: str = Form(...)):
    profile_data = {
        "name": "John Doe",
        "title": "Software Engineer",
        "experience": [
            {"company": "Tech Company", "position": "Senior Engineer", "duration": "3 years"}
        ],
        "skills": ["Python", "FastAPI", "OpenAI"]
    }

    return {"linkedin_data": profile_data}


def generate_prompt_messages(resume_text, job_description):
    prompt = f"""
                   You are a career consultant helping candidates assess how well their resume matches a specific job vacancy. 
                   You will be provided with the candidate's resume and the job description. 
                   Your task is to provide an objective evaluation of how well the resume fits the job requirements, 
                   give feedback, and offer suggestions on how the resume can be improved for a better match.

                   Please provide the result in JSON format (only JSON!! without any additional symbols), containing the following fields:
                   - "score": an integer (0-100) representing the match between the resume and the job description, where 100 means a perfect match.
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
