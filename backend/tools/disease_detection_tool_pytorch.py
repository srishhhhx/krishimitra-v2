"""
PyTorch-based Plant Disease Detection Tool

This module provides disease detection using a ResNet-9 CNN model trained on
the PlantVillage dataset with 38 disease classes across 14 crop types.

Key Features:
- ResNet-9 architecture with residual connections
- 99.2% validation accuracy, 100% test accuracy
- 256x256 input images (RGB)
- Device-agnostic (CUDA/MPS/CPU auto-detection)
- 38 disease classes including healthy variants

Model Architecture:
    Input (3×256×256)
      ↓ Conv1 (64) + BatchNorm + ReLU
      ↓ Conv2 (128) + BatchNorm + ReLU + MaxPool
      ↓ Residual Block (128→128)
      ↓ Conv3 (256) + BatchNorm + ReLU + MaxPool
      ↓ Conv4 (512) + BatchNorm + ReLU + MaxPool
      ↓ Residual Block (512→512)
      ↓ Classifier (MaxPool + Flatten + Linear)
    Output (38 classes)
"""

import os
import base64
from io import BytesIO
from typing import Dict, Any, Optional, List
import numpy as np
from PIL import Image

# PyTorch imports
import torch
import torch.nn as nn
import torch.nn.functional as F
import torchvision.transforms as transforms

from langchain.tools import tool
from core.logging import get_logger

logger = get_logger(__name__)


# ============================================================================
# ResNet-9 Model Architecture
# ============================================================================


def ConvBlock(in_channels: int, out_channels: int, pool: bool = False) -> nn.Sequential:
    """
    Convolutional block with BatchNormalization and ReLU activation
    
    Args:
        in_channels: Number of input channels
        out_channels: Number of output channels
        pool: Whether to add MaxPool2d layer
        
    Returns:
        Sequential module with Conv2d, BatchNorm2d, ReLU, and optional MaxPool2d
    """
    layers = [
        nn.Conv2d(in_channels, out_channels, kernel_size=3, padding=1),
        nn.BatchNorm2d(out_channels),
        nn.ReLU(inplace=True)
    ]
    if pool:
        layers.append(nn.MaxPool2d(4))
    return nn.Sequential(*layers)


class ResNet9(nn.Module):
    """
    ResNet-9 architecture for plant disease classification
    
    This is a custom 9-layer residual network with:
    - 4 convolutional blocks
    - 2 residual blocks (skip connections)
    - Batch normalization for training stability
    - MaxPooling for spatial dimension reduction
    
    Architecture achieves 99.2% validation accuracy on PlantVillage dataset.
    """
    
    def __init__(self, in_channels: int = 3, num_classes: int = 38):
        """
        Initialize ResNet-9 model
        
        Args:
            in_channels: Number of input channels (3 for RGB)
            num_classes: Number of output classes (38 for PlantVillage)
        """
        super().__init__()
        
        self.conv1 = ConvBlock(in_channels, 64)
        self.conv2 = ConvBlock(64, 128, pool=True)  # out: 128 x 64 x 64
        self.res1 = nn.Sequential(ConvBlock(128, 128), ConvBlock(128, 128))
        
        self.conv3 = ConvBlock(128, 256, pool=True)  # out: 256 x 16 x 16
        self.conv4 = ConvBlock(256, 512, pool=True)  # out: 512 x 4 x 4
        self.res2 = nn.Sequential(ConvBlock(512, 512), ConvBlock(512, 512))
        
        self.classifier = nn.Sequential(
            nn.MaxPool2d(4),
            nn.Flatten(),
            nn.Linear(512, num_classes)
        )
        
    def forward(self, xb: torch.Tensor) -> torch.Tensor:
        """
        Forward pass through the network
        
        Args:
            xb: Input batch tensor of shape (N, 3, 256, 256)
            
        Returns:
            Output logits of shape (N, num_classes)
        """
        out = self.conv1(xb)
        out = self.conv2(out)
        out = self.res1(out) + out  # Residual connection
        out = self.conv3(out)
        out = self.conv4(out)
        out = self.res2(out) + out  # Residual connection
        out = self.classifier(out)
        return out


# ============================================================================
# Disease Detection Service
# ============================================================================


class PyTorchDiseaseDetectionService:
    """
    Service for detecting plant diseases using PyTorch ResNet-9 model
    
    This service handles:
    - Model loading with multiple strategies (state_dict, full model, legacy)
    - Device auto-detection (CUDA/MPS/CPU)
    - Image preprocessing and prediction
    - Treatment recommendations for detected diseases
    """
    
    # Class names (38 disease categories)
    CLASS_NAMES = [
        "Apple___Apple_scab",
        "Apple___Black_rot",
        "Apple___Cedar_apple_rust",
        "Apple___healthy",
        "Blueberry___healthy",
        "Cherry_(including_sour)___Powdery_mildew",
        "Cherry_(including_sour)___healthy",
        "Corn_(maize)___Cercospora_leaf_spot Gray_leaf_spot",
        "Corn_(maize)___Common_rust_",
        "Corn_(maize)___Northern_Leaf_Blight",
        "Corn_(maize)___healthy",
        "Grape___Black_rot",
        "Grape___Esca_(Black_Measles)",
        "Grape___Leaf_blight_(Isariopsis_Leaf_Spot)",
        "Grape___healthy",
        "Orange___Haunglongbing_(Citrus_greening)",
        "Peach___Bacterial_spot",
        "Peach___healthy",
        "Pepper,_bell___Bacterial_spot",
        "Pepper,_bell___healthy",
        "Potato___Early_blight",
        "Potato___Late_blight",
        "Potato___healthy",
        "Raspberry___healthy",
        "Soybean___healthy",
        "Squash___Powdery_mildew",
        "Strawberry___Leaf_scorch",
        "Strawberry___healthy",
        "Tomato___Bacterial_spot",
        "Tomato___Early_blight",
        "Tomato___Late_blight",
        "Tomato___Leaf_Mold",
        "Tomato___Septoria_leaf_spot",
        "Tomato___Spider_mites Two-spotted_spider_mite",
        "Tomato___Target_Spot",
        "Tomato___Tomato_Yellow_Leaf_Curl_Virus",
        "Tomato___Tomato_mosaic_virus",
        "Tomato___healthy"
    ]
    
    # Treatment recommendations
    TREATMENTS = {
        "Apple___Apple_scab": {
            "treatment": "Apply fungicides containing captan or sulfur. Remove infected leaves and improve air circulation.",
            "preventive": ["Choose resistant varieties", "Prune trees for better air circulation", "Remove fallen leaves"]
        },
        "Apple___Black_rot": {
            "treatment": "Remove infected fruit and branches. Apply fungicides during wet periods.",
            "preventive": ["Prune dead wood", "Remove mummified fruit", "Apply dormant spray"]
        },
        "Apple___Cedar_apple_rust": {
            "treatment": "Apply fungicides in spring. Remove nearby cedar trees if possible.",
            "preventive": ["Plant resistant varieties", "Remove galls from cedar trees", "Apply preventive fungicides"]
        },
        "Tomato___Early_blight": {
            "treatment": "Apply chlorothalonil or copper-based fungicides. Remove affected leaves.",
            "preventive": ["Rotate crops", "Mulch around plants", "Water at base of plants"]
        },
        "Tomato___Late_blight": {
            "treatment": "Apply fungicides immediately. Remove and destroy infected plants.",
            "preventive": ["Use resistant varieties", "Ensure good air circulation", "Avoid overhead watering"]
        },
        "Potato___Early_blight": {
            "treatment": "Apply fungicides containing chlorothalonil. Remove infected foliage.",
            "preventive": ["Rotate crops yearly", "Use certified disease-free seed", "Maintain plant vigor"]
        },
        "Potato___Late_blight": {
            "treatment": "Apply fungicides immediately. Destroy infected plants.",
            "preventive": ["Plant resistant varieties", "Avoid overhead irrigation", "Hill soil around plants"]
        },
        # Add more treatments as needed
    }
    
    def __init__(self, model_path: str = "models/disease_detection_state_dict.pth"):
        """
        Initialize the disease detection service
        
        Args:
            model_path: Path to the PyTorch model file
        """
        self.model_path = model_path
        self.device = self._get_device()
        self.model = None
        self.transform = self._get_transform()
        self.model_loaded = False
        
        # Load model
        self._load_model()
        
    def _get_device(self) -> torch.device:
        """
        Auto-detect best available device (CUDA > MPS > CPU)
        
        Returns:
            torch.device object
        """
        if torch.cuda.is_available():
            device = torch.device("cuda")
            logger.info(f"Using CUDA device: {torch.cuda.get_device_name(0)}")
        elif hasattr(torch.backends, 'mps') and torch.backends.mps.is_available():
            device = torch.device("mps")
            logger.info("Using Apple Silicon MPS device")
        else:
            device = torch.device("cpu")
            logger.info("Using CPU device")
        return device
    
    def _get_transform(self) -> transforms.Compose:
        """
        Get image transformation pipeline
        
        Returns:
            Composed transforms for preprocessing
        """
        return transforms.Compose([
            transforms.Resize((256, 256)),
            transforms.ToTensor(),  # Converts to [0, 1] and changes to (C, H, W)
        ])
    
    def _load_model(self):
        """
        Load PyTorch model with multiple fallback strategies
        
        Strategies:
        1. Load state_dict (recommended format)
        2. Load full model object (legacy format)
        3. Load with weights_only=False (for older models)
        """
        if not os.path.exists(self.model_path):
            logger.error(f"Model file not found: {self.model_path}")
            logger.warning("Service will start without model functionality")
            return
        
        try:
            # Strategy 1: Try loading as state_dict (recommended)
            logger.info(f"Loading model from: {self.model_path}")
            self.model = ResNet9(in_channels=3, num_classes=len(self.CLASS_NAMES))
            
            try:
                state_dict = torch.load(self.model_path, map_location=self.device)
                self.model.load_state_dict(state_dict)
                logger.info("✓ Model loaded successfully (state_dict format)")
                self.model_loaded = True
            except Exception as e1:
                logger.warning(f"Failed to load as state_dict: {e1}")
                
                # Strategy 2: Try loading full model object
                try:
                    logger.info("Attempting to load full model object (legacy format)...")
                    self.model = torch.load(
                        self.model_path,
                        map_location=self.device,
                        weights_only=False
                    )
                    logger.info("✓ Model loaded successfully (full object format)")
                    self.model_loaded = True
                except Exception as e2:
                    logger.error(f"Failed to load full model object: {e2}")
                    raise Exception(f"All loading strategies failed")
            
            # Move model to device and set to eval mode
            self.model = self.model.to(self.device)
            self.model.eval()
            
            # Log model info
            total_params = sum(p.numel() for p in self.model.parameters())
            logger.info(f"Model parameters: {total_params:,}")
            logger.info(f"Model device: {self.device}")
            
        except Exception as e:
            logger.error(f"Error loading model: {e}")
            logger.warning("Model loading failed. Service will start without model functionality.")
            self.model = None
            self.model_loaded = False
    
    def _preprocess_image(self, image: Image.Image) -> torch.Tensor:
        """
        Preprocess image for model input
        
        Args:
            image: PIL Image object
            
        Returns:
            Preprocessed tensor of shape (1, 3, 256, 256)
        """
        # Convert to RGB if needed
        if image.mode != 'RGB':
            image = image.convert('RGB')
        
        # Apply transforms
        img_tensor = self.transform(image)
        
        # Add batch dimension
        img_tensor = img_tensor.unsqueeze(0)
        
        return img_tensor
    
    def predict(
        self,
        image_base64: str,
        confidence_threshold: float = 0.7,
        crop_type_hint: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Predict disease from base64-encoded image
        
        Args:
            image_base64: Base64-encoded image string
            confidence_threshold: Minimum confidence for prediction (0-1)
            crop_type_hint: Optional crop type hint from user query
            
        Returns:
            Dictionary with prediction results
        """
        if not self.model_loaded:
            return {
                "error": "Model not loaded",
                "help": "The disease detection model failed to load. Please check model file."
            }
        
        try:
            # Decode base64 image
            image_data = base64.b64decode(image_base64)
            image = Image.open(BytesIO(image_data))
            
            # Preprocess
            img_tensor = self._preprocess_image(image)
            img_tensor = img_tensor.to(self.device)
            
            # Predict
            with torch.no_grad():
                outputs = self.model(img_tensor)
                probabilities = F.softmax(outputs, dim=1)
                confidence, predicted_idx = torch.max(probabilities, dim=1)
                
                confidence = confidence.item()
                predicted_idx = predicted_idx.item()
            
            # Get predicted class
            predicted_class = self.CLASS_NAMES[predicted_idx]
            crop, disease = predicted_class.split("___")
            
            # Check confidence threshold
            if confidence < confidence_threshold:
                return {
                    "error": "Low confidence prediction",
                    "confidence_percentage": round(confidence * 100, 2),
                    "predicted_class": predicted_class,
                    "help": f"Model confidence ({confidence*100:.1f}%) is below threshold ({confidence_threshold*100:.0f}%). Image may be unclear or disease not in training data."
                }
            
            # Check if healthy
            is_healthy = disease.lower() == "healthy"
            
            # Get treatment recommendations
            treatment_key = predicted_class
            treatment_info = self.TREATMENTS.get(treatment_key, {
                "treatment": "Consult with a local agricultural expert for specific treatment recommendations.",
                "preventive": ["Maintain good plant hygiene", "Monitor plants regularly", "Ensure proper nutrition"]
            })
            
            # Validate crop type if hint provided
            crop_match = self._validate_crop_type(crop, crop_type_hint)
            
            # Estimate severity
            severity = self._estimate_severity(confidence, is_healthy)
            
            result = {
                "disease_name": disease.replace("_", " "),
                "crop": crop.replace("_", " "),
                "is_healthy": is_healthy,
                "confidence_percentage": round(confidence * 100, 2),
                "severity": severity,
                "treatment": treatment_info["treatment"],
                "preventive_measures": treatment_info["preventive"],
                "crop_type_match": crop_match,
                "predicted_class": predicted_class
            }
            
            logger.info(f"Prediction: {predicted_class} ({confidence*100:.1f}%)")
            return result
            
        except Exception as e:
            logger.error(f"Prediction error: {e}", exc_info=True)
            return {
                "error": f"Prediction failed: {str(e)}",
                "help": "Please ensure the image is valid and try again."
            }
    
    def _validate_crop_type(
        self,
        detected_crop: str,
        crop_hint: Optional[str]
    ) -> Dict[str, Any]:
        """
        Validate detected crop against user's hint
        
        Args:
            detected_crop: Crop detected by model
            crop_hint: Crop type from user query
            
        Returns:
            Dictionary with validation result
        """
        if not crop_hint:
            return {"match": None, "message": ""}
        
        # Normalize for comparison
        detected_normalized = detected_crop.lower().replace("_", " ").replace(",", "")
        hint_normalized = crop_hint.lower().replace("_", " ").replace(",", "")
        
        # Check if hint is in detected crop name
        if hint_normalized in detected_normalized or detected_normalized in hint_normalized:
            return {
                "match": True,
                "message": f"✓ Crop type matches: {crop_hint}"
            }
        else:
            return {
                "match": False,
                "message": f"⚠️ Warning: Model detected {detected_crop}, but you mentioned {crop_hint}. Please verify the crop type."
            }
    
    def _estimate_severity(self, confidence: float, is_healthy: bool) -> str:
        """
        Estimate disease severity based on confidence
        
        Args:
            confidence: Model confidence score
            is_healthy: Whether plant is healthy
            
        Returns:
            Severity level string
        """
        if is_healthy:
            return "none"
        
        if confidence >= 0.9:
            return "severe"
        elif confidence >= 0.8:
            return "moderate"
        else:
            return "mild"
    
    def get_supported_crops(self) -> List[str]:
        """
        Get list of supported crop types
        
        Returns:
            List of unique crop names
        """
        crops = set()
        for class_name in self.CLASS_NAMES:
            crop = class_name.split("___")[0]
            crops.add(crop.replace("_", " "))
        return sorted(list(crops))
    
    def get_model_info(self) -> Dict[str, Any]:
        """
        Get model information
        
        Returns:
            Dictionary with model metadata
        """
        return {
            "model_type": "ResNet-9",
            "framework": "PyTorch",
            "input_size": "256x256",
            "num_classes": len(self.CLASS_NAMES),
            "device": str(self.device),
            "model_loaded": self.model_loaded,
            "accuracy": "99.2% (validation), 100% (test)",
            "parameters": sum(p.numel() for p in self.model.parameters()) if self.model else 0
        }


# ============================================================================
# Global Service Instance
# ============================================================================

# Initialize service
disease_service = PyTorchDiseaseDetectionService()


# ============================================================================
# LangChain Tool Wrapper
# ============================================================================

@tool
def detect_plant_disease_pytorch(
    image_base64: str,
    crop_type_hint: Optional[str] = None,
    confidence_threshold: float = 0.7
) -> Dict[str, Any]:
    """
    Detect plant disease from image using PyTorch ResNet-9 model.
    
    This tool uses a deep learning model trained on 87K images across 38 disease
    classes to identify plant diseases with 99.2% accuracy.
    
    Args:
        image_base64: Base64-encoded image of the plant leaf
        crop_type_hint: Optional crop type mentioned by user (e.g., "tomato", "potato")
        confidence_threshold: Minimum confidence for prediction (default: 0.7)
    
    Returns:
        Dictionary containing:
        - disease_name: Name of detected disease
        - crop: Detected crop type
        - is_healthy: Whether plant is healthy
        - confidence_percentage: Model confidence (0-100)
        - severity: Disease severity (mild/moderate/severe/none)
        - treatment: Treatment recommendations
        - preventive_measures: List of preventive measures
        - crop_type_match: Validation against user's crop hint
    
    Example:
        >>> result = detect_plant_disease_pytorch(
        ...     image_base64="iVBORw0KGgoAAAANS...",
        ...     crop_type_hint="tomato"
        ... )
        >>> print(result["disease_name"])
        "Late blight"
    """
    return disease_service.predict(
        image_base64=image_base64,
        confidence_threshold=confidence_threshold,
        crop_type_hint=crop_type_hint
    )
