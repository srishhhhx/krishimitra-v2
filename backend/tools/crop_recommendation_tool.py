"""
Crop Recommendation Tool

Recommends optimal crops based on soil nutrients (N, P, K) and environmental conditions
(temperature, humidity, pH, rainfall) using a Naive Bayes classifier.

Model: NBClassifier.pkl (Naive Bayes trained on agricultural dataset)
Input: 7 parameters (N, P, K, temperature, humidity, pH, rainfall)
Output: Recommended crop with confidence score and alternatives
"""

import pickle
from pathlib import Path
from typing import Dict, Any, List
import numpy as np
import pandas as pd

from langchain.tools import tool
from core.logging import get_logger

logger = get_logger(__name__)


# ============================================================================
# Model Loading
# ============================================================================

MODEL_PATH = Path(__file__).resolve().parent.parent / "models" / "NBClassifier.pkl"

try:
    with open(MODEL_PATH, "rb") as file:
        crop_model = pickle.load(file)
    logger.info(f"✓ Crop recommendation model loaded from {MODEL_PATH}")

    # Get crop classes if available
    if hasattr(crop_model, 'classes_'):
        CROP_CLASSES = crop_model.classes_.tolist()
        logger.info(f"✓ Model supports {len(CROP_CLASSES)} crop classes")
    else:
        CROP_CLASSES = []
        logger.warning("⚠️ Model classes not available")

except FileNotFoundError:
    logger.error(f"❌ Model file not found: {MODEL_PATH}")
    crop_model = None
    CROP_CLASSES = []
except Exception as e:
    logger.error(f"❌ Failed to load crop model: {e}")
    crop_model = None
    CROP_CLASSES = []


# ============================================================================
# Default Values for Missing Parameters
# ============================================================================

# These are sensible defaults based on typical Indian agricultural conditions
DEFAULT_VALUES = {
    "N": 50.0,          # Nitrogen (kg/ha) - moderate
    "P": 50.0,          # Phosphorus (kg/ha) - moderate
    "K": 50.0,          # Potassium (kg/ha) - moderate
    "temperature": 25.0,  # Temperature (°C) - typical Indian average
    "humidity": 65.0,   # Humidity (%) - moderate
    "ph": 6.5,          # pH - neutral to slightly acidic
    "rainfall": 100.0   # Rainfall (mm) - moderate
}


# ============================================================================
# Helper Functions
# ============================================================================

def validate_parameters(
    N: float,
    P: float,
    K: float,
    temperature: float,
    humidity: float,
    ph: float,
    rainfall: float
) -> Dict[str, Any]:
    """
    Validate input parameters and return validation results.

    Returns:
        Dict with 'valid' (bool) and 'errors' (list) keys
    """
    errors = []

    # NPK validation (non-negative)
    if N < 0:
        errors.append("Nitrogen (N) must be non-negative")
    if P < 0:
        errors.append("Phosphorus (P) must be non-negative")
    if K < 0:
        errors.append("Potassium (K) must be non-negative")

    # Temperature validation (-10 to 60°C)
    if temperature < -10 or temperature > 60:
        errors.append("Temperature must be between -10 and 60°C")

    # Humidity validation (0-100%)
    if humidity < 0 or humidity > 100:
        errors.append("Humidity must be between 0 and 100%")

    # pH validation (0-14)
    if ph < 0 or ph > 14:
        errors.append("pH must be between 0 and 14")

    # Rainfall validation (non-negative)
    if rainfall < 0:
        errors.append("Rainfall must be non-negative")

    return {
        "valid": len(errors) == 0,
        "errors": errors
    }


def get_top_recommendations(
    probabilities: np.ndarray,
    classes: List[str],
    top_n: int = 5
) -> List[Dict[str, Any]]:
    """
    Get top N crop recommendations with confidence scores.

    Args:
        probabilities: Model probability output (1D array)
        classes: List of crop class names
        top_n: Number of recommendations to return

    Returns:
        List of dicts with 'crop' and 'confidence' keys
    """
    # Get indices of top N probabilities
    top_indices = np.argsort(probabilities[0])[::-1][:top_n]

    recommendations = []
    for idx in top_indices:
        crop_name = classes[idx]
        confidence = float(probabilities[0][idx]) * 100  # Convert to percentage

        recommendations.append({
            "crop": crop_name,
            "confidence_percentage": round(confidence, 2)
        })

    return recommendations


# ============================================================================
# LangChain Tool Wrapper
# ============================================================================

@tool
def recommend_crop(
    N: float,
    P: float,
    K: float,
    temperature: float,
    humidity: float,
    ph: float,
    rainfall: float
) -> Dict[str, Any]:
    """
    Recommend optimal crop based on soil nutrients and environmental conditions.

    This tool uses a Naive Bayes classifier trained on agricultural data to predict
    the best crop to plant given soil and climate parameters.

    Args:
        N: Nitrogen content in soil (kg/ha), typical range: 0-140
        P: Phosphorus content in soil (kg/ha), typical range: 5-145
        K: Potassium content in soil (kg/ha), typical range: 5-205
        temperature: Average temperature (°C), range: -10 to 60
        humidity: Relative humidity (%), range: 0-100
        ph: Soil pH value, range: 0-14 (neutral=7)
        rainfall: Annual rainfall (mm), typical range: 20-300

    Returns:
        Dictionary containing:
        - recommended_crop: Primary crop recommendation
        - confidence_percentage: Confidence score (0-100)
        - alternatives: List of alternative crops with confidence scores
        - input_parameters: Echo of input values for verification
        - metadata: Additional information about the prediction

    Example:
        >>> result = recommend_crop(N=90, P=42, K=43, temperature=20.8, humidity=82, ph=6.5, rainfall=202)
        >>> print(result['recommended_crop'])
        'rice'
        >>> print(result['confidence_percentage'])
        95.2
    """
    try:
        # Check if model is loaded
        if crop_model is None:
            return {
                "error": "Crop recommendation model not available",
                "recommended_crop": None,
                "confidence_percentage": 0.0,
                "alternatives": []
            }

        # Validate parameters
        validation = validate_parameters(N, P, K, temperature, humidity, ph, rainfall)
        if not validation["valid"]:
            return {
                "error": f"Invalid parameters: {'; '.join(validation['errors'])}",
                "recommended_crop": None,
                "confidence_percentage": 0.0,
                "alternatives": []
            }

        # Prepare input DataFrame with proper column names (same order as training data)
        # This prevents sklearn warning about feature names
        input_data = pd.DataFrame({
            'N': [N],
            'P': [P],
            'K': [K],
            'temperature': [temperature],
            'humidity': [humidity],
            'ph': [ph],
            'rainfall': [rainfall]
        })

        # Get prediction and probabilities
        prediction = crop_model.predict(input_data)
        probabilities = crop_model.predict_proba(input_data)

        # Get top crop
        recommended_crop = prediction[0]

        # Get top recommendations with confidence scores
        recommendations = get_top_recommendations(
            probabilities,
            CROP_CLASSES if CROP_CLASSES else [recommended_crop],
            top_n=5
        )

        # Extract top crop confidence
        top_confidence = recommendations[0]["confidence_percentage"] if recommendations else 0.0

        # Get alternatives (exclude top recommendation)
        alternatives = recommendations[1:] if len(recommendations) > 1 else []

        logger.info(
            f"Crop recommendation: {recommended_crop} "
            f"(confidence: {top_confidence:.2f}%) "
            f"| N={N}, P={P}, K={K}, temp={temperature}, "
            f"humidity={humidity}, pH={ph}, rainfall={rainfall}"
        )

        return {
            "recommended_crop": recommended_crop,
            "confidence_percentage": top_confidence,
            "alternatives": alternatives,
            "input_parameters": {
                "nitrogen": N,
                "phosphorus": P,
                "potassium": K,
                "temperature": temperature,
                "humidity": humidity,
                "ph": ph,
                "rainfall": rainfall
            },
            "metadata": {
                "model_type": "Naive Bayes Classifier",
                "total_classes": len(CROP_CLASSES) if CROP_CLASSES else 1,
                "default_values_used": False  # Will be updated by agent if defaults are used
            }
        }

    except Exception as e:
        logger.error(f"Crop recommendation failed: {e}", exc_info=True)
        return {
            "error": f"Failed to generate crop recommendation: {str(e)}",
            "recommended_crop": None,
            "confidence_percentage": 0.0,
            "alternatives": []
        }


# ============================================================================
# Utility Functions for Agent Use
# ============================================================================

def get_default_value(parameter_name: str) -> float:
    """
    Get default value for a parameter.

    Args:
        parameter_name: Name of parameter (N, P, K, temperature, humidity, ph, rainfall)

    Returns:
        Default value for the parameter
    """
    return DEFAULT_VALUES.get(parameter_name, 0.0)


def apply_defaults(params: Dict[str, float]) -> Dict[str, float]:
    """
    Apply default values for missing parameters.

    Args:
        params: Dictionary with provided parameters (may be incomplete)

    Returns:
        Complete dictionary with defaults applied for missing values
    """
    complete_params = DEFAULT_VALUES.copy()
    complete_params.update(params)
    return complete_params
