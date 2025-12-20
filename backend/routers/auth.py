from fastapi import APIRouter, HTTPException, Depends
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from datetime import datetime
from db import users_collection
from models.user import UserCreate, UserLogin, UserResponse, UserInfoResponse

from core.security import hash_password, verify_password, create_access_token, decode_access_token

router = APIRouter()
security = HTTPBearer()

# Signup endpoints
@router.post("/signup", response_model=UserResponse)
def signup(user: UserCreate):
    try:
        # Check if user already exists
        if users_collection.find_one({"email": user.email}):
            raise HTTPException(status_code=400, detail="Email already registered")
        
        # Hash password and create user with farmer information
        hashed = hash_password(user.password)
        user_data = {
            # Basic Information
            "email": user.email,
            "password": hashed,
            "full_name": user.full_name,
            
            # Farming Information
            "farm_size": user.farm_size,
            "primary_crops": user.primary_crops,
            
            # Metadata
            "created_at": datetime.utcnow()
        }
        
        result = users_collection.insert_one(user_data)
        
        if not result.inserted_id:
            raise HTTPException(status_code=500, detail="Failed to create user")
            
        return {
            "message": "Farmer registration successful", 
            "email": user.email,
            "full_name": user.full_name
        }
    
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail="Internal server error")


# Login endpoint
@router.post("/login")
def login(user: UserLogin):
    try:
        # Find user in database
        db_user = users_collection.find_one({"email": user.email})
        if not db_user:
            raise HTTPException(status_code=401, detail="Invalid credentials")
        
        # Verify password
        if not verify_password(user.password, db_user["password"]):
            raise HTTPException(status_code=401, detail="Invalid credentials")
        
        # Create JWT token
        token = create_access_token({"email": user.email})
        return {
            "access_token": token, 
            "token_type": "bearer",
            "expires_in": 3600  # 1 hour in seconds
        }
    
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail="Internal server error")

# Protected route
def get_current_user(credentials: HTTPAuthorizationCredentials = Depends(security)):
    token = credentials.credentials
    payload = decode_access_token(token)
    if not payload:
        raise HTTPException(status_code=401, detail="Invalid token")
    
    # Verify user still exists in database
    email = payload.get("email")
    if not email:
        raise HTTPException(status_code=401, detail="Invalid token payload")
    
    user = users_collection.find_one({"email": email})
    if not user:
        raise HTTPException(status_code=401, detail="User not found")
    
    return payload

@router.get("/user/me", response_model=UserInfoResponse)
def get_user(current_user: dict = Depends(get_current_user)):
    # Get full user data from database
    user = users_collection.find_one({"email": current_user["email"]})
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    return {
        "email": user["email"],
        "full_name": user["full_name"],
        "phone_number": user.get("phone_number", ""),
        "primary_crops": user.get("primary_crops", []),
        "farm_size": user.get("farm_size", "")
    }

