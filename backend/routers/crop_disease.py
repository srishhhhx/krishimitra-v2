from fastapi import APIRouter, HTTPException, Depends, UploadFile, File
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from pydantic import BaseModel
from typing import Optional, Dict, Any
import io
from core.security import decode_access_token
from db import users_collection
from services.crop_disease_detection import get_crop_disease_detector

router = APIRouter()
security = HTTPBearer()  # for JWT token

# Response schemas
class DiseaseDetectionResponse(BaseModel):
    success: bool
    prediction: Optional[Dict[str, Any]] = None
    error: Optional[str] = None

class PredictionResult(BaseModel):
    class_name: str
    crop: str
    disease: str
    is_healthy: bool
    confidence: float
    confidence_percentage: float

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

@router.post("/detect-disease", response_model=DiseaseDetectionResponse)
async def detect_crop_disease(
    file: UploadFile = File(...),
    current_user: dict = Depends(get_current_user)
):
    """
    Detect crop disease from uploaded image
    
    Args:
        file: Uploaded image file (JPG, PNG, etc.)
        current_user: Authenticated user
        
    Returns:
        Disease detection results
    """
    try:
        # Validate file type
        if not file.content_type or not file.content_type.startswith('image/'):
            raise HTTPException(
                status_code=400, 
                detail="File must be an image (JPG, PNG, etc.)"
            )
        
        # Read image data
        image_data = await file.read()
        
        if len(image_data) == 0:
            raise HTTPException(status_code=400, detail="Empty file uploaded")
        
        # Make prediction
        detector = get_crop_disease_detector()
        result = detector.predict_disease(image_data)
        
        if result['success']:
            return DiseaseDetectionResponse(
                success=True,
                prediction={
                    **result['prediction'],
                    'farmer_email': current_user['email'],
                    'filename': file.filename
                }
            )
        else:
            raise HTTPException(
                status_code=500, 
                detail=f"Prediction failed: {result['error']}"
            )
            
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")

@router.post("/detect-disease-detailed", response_model=Dict[str, Any])
async def detect_crop_disease_detailed(
    file: UploadFile = File(...),
    current_user: dict = Depends(get_current_user)
):
    """
    Detect crop disease from uploaded image with detailed results
    
    Args:
        file: Uploaded image file (JPG, PNG, etc.)
        current_user: Authenticated user
        
    Returns:
        Detailed disease detection results including all class probabilities
    """
    try:
        # Validate file type
        if not file.content_type or not file.content_type.startswith('image/'):
            raise HTTPException(
                status_code=400, 
                detail="File must be an image (JPG, PNG, etc.)"
            )
        
        # Read image data
        image_data = await file.read()
        
        if len(image_data) == 0:
            raise HTTPException(status_code=400, detail="Empty file uploaded")
        
        # Make prediction
        detector = get_crop_disease_detector()
        result = detector.predict_disease(image_data)
        
        if result['success']:
            # Add user info to result
            result['farmer_email'] = current_user['email']
            result['filename'] = file.filename
            
            # Sort all predictions by confidence
            result['all_predictions'] = sorted(
                result['all_predictions'], 
                key=lambda x: x['confidence'], 
                reverse=True
            )
            
            return result
        else:
            raise HTTPException(
                status_code=500, 
                detail=f"Prediction failed: {result['error']}"
            )
            
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")

@router.get("/supported-crops")
def get_supported_crops():
    """
    Get list of supported crops and diseases
    
    Returns:
        List of supported crop classes
    """
    try:
        # Extract unique crops from class names
        detector = get_crop_disease_detector()
        crops = set()
        diseases_by_crop = {}
        
        for class_name in detector.class_names:
            parts = class_name.split('___')
            crop = parts[0].replace('_', ' ')
            disease = parts[1].replace('_', ' ') if len(parts) > 1 else 'Unknown'
            
            crops.add(crop)
            
            if crop not in diseases_by_crop:
                diseases_by_crop[crop] = []
            diseases_by_crop[crop].append(disease)
        
        return {
            'supported_crops': sorted(list(crops)),
            'diseases_by_crop': diseases_by_crop,
            'total_classes': len(detector.class_names),
            'all_classes': detector.class_names
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error retrieving supported crops: {str(e)}")

@router.get("/model-info")
def get_model_info():
    """
    Get information about the loaded model
    
    Returns:
        Model information and status
    """
    try:
        detector = get_crop_disease_detector()
        model_loaded = detector.model is not None
        
        model_info = {
            'model_loaded': model_loaded,
            'model_path': detector.model_path,
            'total_classes': len(detector.class_names),
            'input_shape': [128, 128, 3] if model_loaded else None,
        }
        
        if model_loaded and detector.model:
            try:
                model_info['model_summary'] = {
                    'input_shape': detector.model.input_shape,
                    'output_shape': detector.model.output_shape,
                    'total_params': detector.model.count_params()
                }
            except Exception as e:
                model_info['model_summary_error'] = str(e)
        
        return model_info
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error retrieving model info: {str(e)}")
