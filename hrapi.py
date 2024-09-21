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
