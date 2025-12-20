from fastapi import APIRouter, HTTPException, Depends
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from pydantic import BaseModel, field_validator
import numpy as np
import pickle
from pathlib import Path
from core.security import decode_access_token
from db import users_collection

router = APIRouter()
security = HTTPBearer()  # for JWT token

# Load model once (resolve path relative to backend directory)
MODEL_PATH = Path(__file__).resolve().parent.parent / "models" / "NBClassifier.pkl"
try:
    with open(MODEL_PATH, "rb") as file:
        model = pickle.load(file)
except FileNotFoundError:
    raise RuntimeError("Model file not found. Please ensure models/NBClassifier.pkl exists.")
except Exception as e:
    raise RuntimeError(f"Failed to load crop prediction model: {str(e)}")

# Request schema
class CropFeatures(BaseModel):
    N: float
    P: float
    K: float
    temperature: float
    humidity: float
    ph: float
    rainfall: float

    # Validators with helpful messages for UI
    @field_validator("temperature")
    @classmethod
    def validate_temperature(cls, v: float) -> float:
        if v < -10 or v > 60:
            raise ValueError("Temperature must be between -10 and 60 °C")
        return v

    @field_validator("humidity")
    @classmethod
    def validate_humidity(cls, v: float) -> float:
        if v < 0 or v > 100:
            raise ValueError("Humidity must be between 0 and 100%")
        return v

    @field_validator("ph")
    @classmethod
    def validate_ph(cls, v: float) -> float:
        if v < 0 or v > 14:
            raise ValueError("pH must be between 0 and 14")
        return v

    @field_validator("N", "P", "K", "rainfall")
    @classmethod
    def validate_non_negative(cls, v: float) -> float:
        if v < 0:
            raise ValueError("Values must be non-negative")
        return v

# Dependency to get current user from token
def get_current_user(credentials: HTTPAuthorizationCredentials = Depends(security)):
    token = credentials.credentials
    payload = decode_access_token(token)
    if not payload:
        raise HTTPException(status_code=401, detail="Invalid token")
    
    email = payload.get("email")
    user = users_collection.find_one({"email": email})
    if not user:
        raise HTTPException(status_code=401, detail="User not found")
    
    return user

# Protected endpoint
@router.post("/predict")
def predict_crop(features: CropFeatures, current_user: dict = Depends(get_current_user)):
    try:
        data = np.array([[features.N, features.P, features.K, features.temperature,
                          features.humidity, features.ph, features.rainfall]])
        prediction = model.predict(data)
        return {"predicted_crop": prediction[0], "farmer_email": current_user["email"]}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
