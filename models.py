from sqlalchemy import Column, Integer, String, create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker

Base = declarative_base()

# User model
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

# Verification model
class Verification(Base):
    __tablename__ = 'verifications'
    id = Column(Integer, primary_key=True, index=True)
    email_hash = Column(String, unique=True, index=True)  # Store hashed email
    verified = Column(String, default="not")  # Can be 'not', 'device', or 'orb'

# Database setup
DATABASE_URL = "sqlite:///./test.db"
engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# Create the tables in the database
Base.metadata.create_all(bind=engine)
