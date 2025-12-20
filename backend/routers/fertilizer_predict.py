from fastapi import APIRouter, HTTPException, Depends
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from pydantic import BaseModel
import numpy as np
import joblib
from core.security import decode_access_token
from db import users_collection

router = APIRouter()
security = HTTPBearer()

# Load model and fertilizer mapping once
try:
    xgb_model = joblib.load("models/xgb_pipeline.joblib")
    fert_dict = joblib.load("models/fertname_dict.joblib")
    print("✅ XGBoost fertilizer model loaded successfully!")
except Exception as e:
    print("❌ Error loading fertilizer model:", e)
    xgb_model = None
    fert_dict = {}

# Schema for input
class FertilizerFeatures(BaseModel):
    Temperature: float
    Humidity: float
    Moisture: float
    SoilType: int
    CropType: int
    Nitrogen: float
    Phosphorous: float
    Potassium: float

# Dependency to get current authenticated user
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

# Secure prediction route
@router.post("/predict")
def predict_fertilizer(features: FertilizerFeatures, current_user: dict = Depends(get_current_user)):
    if xgb_model is None:
        raise HTTPException(status_code=500, detail="Model not loaded")

    try:
        data = np.array([[features.Temperature, features.Humidity, features.Moisture,
                          features.SoilType, features.CropType, features.Nitrogen,
                          features.Phosphorous, features.Potassium]])
        pred = xgb_model.predict(data)[0]
        fertilizer_name = fert_dict.get(pred, "Unknown")
        return {
            "recommended_fertilizer": fertilizer_name,
            "farmer_email": current_user["email"]
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
