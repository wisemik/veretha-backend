from fastapi import FastAPI, HTTPException, Depends
from sqlalchemy import Column, Integer, String, create_engine
from sqlalchemy.orm import declarative_base, sessionmaker, Session
from passlib.context import CryptContext
from pydantic import BaseModel, EmailStr
import hashlib
import requests
import os
import uvicorn
from fastapi.middleware.cors import CORSMiddleware
from dotenv import load_dotenv
# Load environment variables from .env file
load_dotenv()


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


# Email verification table
class Verification(Base):
    __tablename__ = 'verifications'
    id = Column(Integer, primary_key=True, index=True)
    email_hash = Column(String, unique=True, index=True)  # Store hashed email
    verified = Column(String, default="not")  # Can be 'not', 'device', or 'orb'


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


# Create the tables in the database
Base.metadata.create_all(bind=engine)

# Password hashing context
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


# Function to hash email
def hash_email(email: str) -> str:
    """Hash the email using SHA256."""
    return hashlib.sha256(email.encode()).hexdigest()


# Dependency to get DB session
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


# Pydantic model for email verification update
class EmailVerificationUpdate(BaseModel):
    email: EmailStr
    verification_status: str


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


# Register a new user
@app.post("/register")
def register_user(user: UserCreate, db: Session = Depends(get_db)):
    # Check if the user is already registered
    db_user = db.query(User).filter(User.email == user.email).first()
    if db_user:
        raise HTTPException(status_code=400, detail="Email already registered")

    # Hash the password
    hashed_password = pwd_context.hash(user.password)

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
        linkedin_url=user.linkedin_url
    )
    db.add(new_user)
    db.commit()

    # Hash the email and store the verification status in the Verification table
    email_hash = hash_email(user.email)
    new_verification = Verification(email_hash=email_hash)
    db.add(new_verification)
    db.commit()

    return {
        "id": new_user.id,
        "email": new_user.email,
        "full_name": new_user.full_name,
        "occupation": new_user.occupation,
        "company": new_user.company,
        "skills": new_user.skills,
        "country": new_user.country,
        "city": new_user.city,
        "linkedin_url": new_user.linkedin_url
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

# Set verification status
@app.post("/set-verified")
def set_verified(email_verification: EmailVerificationUpdate, db: Session = Depends(get_db)):
    email_hash = hash_email(email_verification.email)

    # Find the verification record for the email
    db_verification = db.query(Verification).filter(Verification.email_hash == email_hash).first()

    # Update or create the verification record
    if db_verification:
        db_verification.verified = email_verification.verification_status
    else:
        new_verification = Verification(email_hash=email_hash, verified=email_verification.verification_status)
        db.add(new_verification)

    db.commit()
    return {
        "message": f"Verification status for {email_verification.email} set to {email_verification.verification_status}"}


# Get verification status
@app.get("/get-verified/{email}")
def get_verified(email: str, db: Session = Depends(get_db)):
    # Hash the email
    email_hash = hash_email(email)

    # Find the verification record for the email
    db_verification = db.query(Verification).filter(Verification.email_hash == email_hash).first()

    if not db_verification:
        raise HTTPException(status_code=404, detail="Email not found")

    return {"email": email, "verified": db_verification.verified}


# Login method (for completeness)
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
        "linkedin_url": db_user.linkedin_url
    }

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)
