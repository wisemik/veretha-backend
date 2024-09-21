import hashlib
from fastapi import UploadFile, File, Form, HTTPException, Depends
from pdfminer.high_level import extract_text
import openai
import uvicorn
import json
from dotenv import load_dotenv
from fastapi.middleware.cors import CORSMiddleware
from fastapi import FastAPI
import os
from pydantic import BaseModel, EmailStr
import requests
from sqlalchemy import Column, Integer, String, Boolean, create_engine
from sqlalchemy.orm import declarative_base, sessionmaker, Session
from passlib.context import CryptContext
import circle_veretha

# Load environment variables from .env file
load_dotenv()

PROXYCURL_API_KEY = os.getenv('PROXYCURL_API_KEY')
OPENAI_API_KEY = os.getenv('OPENAI_API_KEY')
openai.api_key = OPENAI_API_KEY

# FastAPI app instance
app = FastAPI()

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Database setup
Base = declarative_base()
DATABASE_URL = "sqlite:///./test.db"
engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# User table for registration
class User(Base):
    __tablename__ = 'users'
    id = Column(Integer, primary_key=True, index=True)
    email = Column(String, unique=True, index=True)
    password = Column(String)
    full_name = Column(String)
    occupation = Column(String)
    company = Column(String)
    skills = Column(String)
    country = Column(String)
    city = Column(String)
    linkedin_url = Column(String)
    verified = Column(Boolean, default=False)  # Changed to Boolean
    wallet_id = Column(String)
    wallet_address = Column(String)

# Create the tables in the database
Base.metadata.create_all(bind=engine)

# Password hashing context
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# Dependency to get DB session
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

def generate_wallet_id_and_address(email: str):
    """Generate wallet_id and wallet_address using the email as a base."""
    wallet_id, wallet_address = circle_veretha.create_wallet(email, email, email)
    return wallet_id, wallet_address

# Pydantic model for user registration
class UserCreate(BaseModel):
    email: EmailStr
    password: str
    full_name: str
    occupation: str = ""
    company: str = ""
    skills: str = ""
    country: str = ""
    city: str = ""
    linkedin_url: str = ""
    verified: bool = False  # Changed to boolean

# Register a new user
@app.post("/register")
def register_user(user: UserCreate, db: Session = Depends(get_db)):
    # Check if the user is already registered
    db_user = db.query(User).filter(User.email == user.email).first()
    if db_user:
        raise HTTPException(status_code=400, detail="Email already registered")

    # Hash the password
    hashed_password = pwd_context.hash(user.password)

    wallet_id, wallet_address = generate_wallet_id_and_address(user.email)

    # Create new user entry
    new_user = User(
        email=user.email,
        password=hashed_password,
        full_name=user.full_name,
        occupation=user.occupation,
        company=user.company,
        skills=user.skills,
        country=user.country,
        city=user.city,
        linkedin_url=user.linkedin_url,
        verified=user.verified,  # Accept boolean
        wallet_id=wallet_id,
        wallet_address=wallet_address
    )
    db.add(new_user)
    db.commit()

    print(f"New user registered: {new_user.wallet_address}, {new_user.wallet_id}")
    return {
        "id": new_user.id,
        "email": new_user.email,
        "full_name": new_user.full_name,
        "occupation": new_user.occupation,
        "company": new_user.company,
        "skills": new_user.skills,
        "country": new_user.country,
        "city": new_user.city,
        "linkedin_url": new_user.linkedin_url,
        "verified": new_user.verified,  # Return boolean
        "wallet_id": new_user.wallet_id,
        "wallet_address": new_user.wallet_address
    }

@app.get("/get-balance/{wallet_id}")
def get_balance(wallet_id: str):
    return {"balance": circle_veretha.wallet_balance(wallet_id)}

@app.get("/pay")
def pay():
    circle_veretha.create_transfer("f89bfdb1-ccf3-517a-8046-12cffeb406de", "10",
                                   "0x87568c541a2d09416ff92f05bd9ca3ffbf2c020e")

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

class LinkedInRequest(BaseModel):
    linkedin_url: str
@app.post("/extract-linkedin")
async def extract_linkedin(linkedin_request: LinkedInRequest):
    linkedin_url = linkedin_request.linkedin_url
    print(f"Received LinkedIn URL: {linkedin_url}")
    profile_data = fetch_linkedin_profile(linkedin_url)
    print(f"Profile data: {profile_data}")

    return {"linkedin_data": profile_data}


def generate_prompt_messages(resume_text, job_description):
    prompt = f"""
                   You are a career consultant helping candidates assess how well their resume matches
                    a specific job vacancy. 
                   You will be provided with the candidate's resume and the job description. 
                   Your task is to provide an objective evaluation of how well the resume fits the job requirements, 
                   give feedback, and offer suggestions on how the resume can be improved for a better match.
                    
                    Don't be  critical, give a good feedack.
                    
                   Please provide the result in JSON format (only JSON!! without any additional symbols), containing the
                    following fields:
                   - "score": a string  (0-100) representing the match between the resume and the job description, where
                    0 - no match at all and 100 means a absolutely perfect match.
                   - "description": a string containing feedback on the score: why that score, and how well the resume
                    fits the job requirements.
                   - "details": a string containing html with suggestions for improving the resume to better match the
                    job description in form of multiple suggestions. 


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

class ScoreRequest(BaseModel):
    resume_text: str
    job_description: str


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


@app.get("/get-profile/{email}")
def get_profile(email: str, db: Session = Depends(get_db)):
    # Find the user by email
    db_user = db.query(User).filter(User.email == email).first()

    # If user is not found, raise an error
    if not db_user:
        raise HTTPException(status_code=404, detail="User not found")

    # Return the user's profile details
    return {
        "id": db_user.id,
        "email": db_user.email,
        "full_name": db_user.full_name,
        "occupation": db_user.occupation,
        "company": db_user.company,
        "skills": db_user.skills,
        "country": db_user.country,
        "city": db_user.city,
        "linkedin_url": db_user.linkedin_url,
        "verified": db_user.verified,  # Return boolean
        "wallet_id": db_user.wallet_id,
        "wallet_address": db_user.wallet_address
    }


class VerifyRequest(BaseModel):
    nullifier_hash: str
    merkle_root: str
    proof: str
    verification_level: str
    action: str

@app.post("/verify")
async def verify(req_body: VerifyRequest):
    print("Received request to verify credential:\n", req_body)

    payload = {
        "nullifier_hash": req_body.nullifier_hash,
        "merkle_root": req_body.merkle_root,
        "proof": req_body.proof,
        "verification_level": req_body.verification_level,
        "action": req_body.action
    }

    print("Sending request to World ID /verify endpoint:\n", payload)

    verify_endpoint = f"{os.getenv('NEXT_PUBLIC_WLD_API_BASE_URL')}/api/v1/verify/{os.getenv('NEXT_PUBLIC_WLD_APP_ID')}"

    try:
        verify_res = requests.post(verify_endpoint, json=payload)
        wld_response = verify_res.json()
        print(f"Received {verify_res.status_code} response from World ID /verify endpoint:\n", wld_response)

        if verify_res.status_code == 200:
            print("Credential verified! This user's nullifier hash is: ", wld_response["nullifier_hash"])
            return {"code": "success", "detail": "This action verified correctly!"}
        else:
            raise HTTPException(status_code=verify_res.status_code, detail=wld_response["detail"])

    except requests.exceptions.RequestException as e:
        print(f"Error occurred: {e}")
        raise HTTPException(status_code=500, detail="Error communicating with World ID verification service.")


# Model to handle verification status update
class EmailModel(BaseModel):
    email: EmailStr

@app.post("/set-verified")
def set_verified(email_model: EmailModel, db: Session = Depends(get_db)):
    # Find the user by email
    email = email_model.email
    print(f"Setting verification status for user {email} to True")
    db_user = db.query(User).filter(User.email == email).first()

    # If user is not found, raise an error
    if not db_user:
        raise HTTPException(status_code=404, detail="User not found")

    # Update the user's verification status to True
    db_user.verified = True  # Always set to True
    db.commit()
    db.refresh(db_user)

    return {"message": f"User {db_user.email} verification status updated to {db_user.verified}"}


# Login method
class UserAuth(BaseModel):
    email: EmailStr
    password: str

@app.post("/login")
def login_user(user: UserAuth, db: Session = Depends(get_db)):
    # Find the user by email
    db_user = db.query(User).filter(User.email == user.email).first()

    # Check if user exists and password is valid
    if not db_user or not pwd_context.verify(user.password, db_user.password):
        raise HTTPException(status_code=400, detail="Invalid credentials")

    return {
        "id": db_user.id,
        "email": db_user.email,
        "full_name": db_user.full_name,
        "occupation": db_user.occupation,
        "company": db_user.company,
        "skills": db_user.skills,
        "country": db_user.country,
        "city": db_user.city,
        "linkedin_url": db_user.linkedin_url,
        "verified": db_user.verified,  # Return boolean
        "wallet_id": db_user.wallet_id,
        "wallet_address": db_user.wallet_address
    }

# File upload and text extraction
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

# Start the app
if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)
