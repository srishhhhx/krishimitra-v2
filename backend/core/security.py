from datetime import datetime, timedelta
from jose import jwt, JWTError
from passlib.context import CryptContext
from dotenv import load_dotenv
import os

# Load .env file
load_dotenv()

# --- JWT Settings ---
JWT_SECRET = os.getenv("JWT_SECRET", "your_fallback_secret")
JWT_ALGORITHM = os.getenv("JWT_ALGORITHM", "HS256")
JWT_EXPIRE_MINUTES = int(os.getenv("JWT_EXPIRE_MINUTES", 60))

# --- Argon2 Password Hashing ---
pwd_context = CryptContext(schemes=["argon2"], deprecated="auto")

# --- Password Hashing ---
def hash_password(password: str) -> str:
    """Hash password using Argon2 (secure, no length limit)."""
    return pwd_context.hash(password)

def verify_password(password: str, hashed: str) -> bool:
    """Verify password against Argon2 hash."""
    return pwd_context.verify(password, hashed)

# --- JWT Token Creation ---
def create_access_token(data: dict) -> str:
    """Create a JWT access token with expiration."""
    to_encode = data.copy()
    expire = datetime.utcnow() + timedelta(minutes=JWT_EXPIRE_MINUTES)
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, JWT_SECRET, algorithm=JWT_ALGORITHM)

# --- JWT Token Decoding ---
def decode_access_token(token: str):
    """Decode JWT and return payload if valid."""
    try:
        payload = jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
        return payload
    except JWTError:
        return None
