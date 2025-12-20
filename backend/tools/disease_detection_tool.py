"""
Disease Detection Tool

This module provides a LangChain tool that wraps the TensorFlow/Keras crop disease
detection model for use in the multi-agent system.

The tool takes image bytes, detects crop disease using a CNN model, and provides
treatment recommendations for 38 disease classes across 14 crop types.
"""
from typing import Dict, Any, Optional
import time
from langchain.tools import tool

from services.crop_disease_detection import get_crop_disease_detector
from core.logging import get_logger

logger = get_logger(__name__)


# ============================================================================
# Treatment Recommendations for 38 Disease Classes
# ============================================================================

TREATMENT_RECOMMENDATIONS = {
    # Apple diseases
    "Apple___Apple_scab": {
        "treatment": "Apply fungicides like Captan or Myclobutanil every 7-14 days during wet weather. Remove and destroy infected leaves and fruit. Prune trees to improve air circulation.",
        "preventive": ["Choose resistant varieties", "Remove fallen leaves", "Avoid overhead irrigation", "Maintain good air circulation"],
        "severity_factors": {"high_humidity": 1.3, "wet_season": 1.4}
    },
    "Apple___Black_rot": {
        "treatment": "Apply Captan or Mancozeb fungicide. Prune out dead and diseased branches. Remove mummified fruits from tree and ground. Apply dormant spray in early spring.",
        "preventive": ["Remove infected fruit and branches", "Avoid wounding the tree", "Maintain tree vigor", "Apply preventive fungicides"],
        "severity_factors": {"wet_conditions": 1.3, "poor_pruning": 1.2}
    },
    "Apple___Cedar_apple_rust": {
        "treatment": "Apply fungicides like Myclobutanil or Propiconazole starting at bud break. Remove nearby cedar/juniper trees if possible. Rake and destroy fallen leaves.",
        "preventive": ["Plant resistant apple varieties", "Remove alternate hosts (cedar/juniper)", "Apply preventive fungicides in spring"],
        "severity_factors": {"proximity_to_cedar": 1.5, "wet_spring": 1.3}
    },
    "Apple___healthy": {
        "treatment": "No treatment needed. Your apple crop appears healthy! Continue good agricultural practices.",
        "preventive": ["Regular monitoring", "Balanced nutrition", "Proper irrigation", "Pest scouting"],
        "severity_factors": {}
    },

    # Blueberry
    "Blueberry___healthy": {
        "treatment": "No treatment needed. Your blueberry crop appears healthy! Maintain current care practices.",
        "preventive": ["Regular monitoring", "Acidic soil maintenance", "Proper mulching", "Adequate water"],
        "severity_factors": {}
    },

    # Cherry
    "Cherry_(including_sour)___Powdery_mildew": {
        "treatment": "Apply sulfur-based fungicides or Myclobutanil. Prune infected shoots. Improve air circulation. Apply fungicides every 7-10 days during active growth.",
        "preventive": ["Plant in sunny locations", "Avoid excessive nitrogen", "Ensure good air circulation", "Remove infected plant parts"],
        "severity_factors": {"high_humidity": 1.4, "poor_air_flow": 1.3}
    },
    "Cherry_(including_sour)___healthy": {
        "treatment": "No treatment needed. Your cherry crop appears healthy! Continue regular maintenance.",
        "preventive": ["Regular pruning", "Balanced fertilization", "Monitor for pests", "Proper irrigation"],
        "severity_factors": {}
    },

    # Corn/Maize
    "Corn_(maize)___Cercospora_leaf_spot Gray_leaf_spot": {
        "treatment": "Apply fungicides like Azoxystrobin or Propiconazole when disease first appears. Rotate crops. Use resistant hybrids. Bury crop residue.",
        "preventive": ["Crop rotation (2-3 years)", "Use resistant varieties", "Reduce plant density", "Bury or remove crop residue"],
        "severity_factors": {"high_humidity": 1.4, "warm_weather": 1.3, "continuous_maize": 1.5}
    },
    "Corn_(maize)___Common_rust_": {
        "treatment": "Apply fungicides like Propiconazole or Azoxystrobin if severe. Usually not economical to treat. Plant resistant hybrids.",
        "preventive": ["Use rust-resistant hybrids", "Monitor regularly", "Balanced nutrition", "Avoid water stress"],
        "severity_factors": {"cool_humid_weather": 1.4, "susceptible_variety": 1.5}
    },
    "Corn_(maize)___Northern_Leaf_Blight": {
        "treatment": "Apply fungicides like Azoxystrobin or Pyraclostrobin at first sign of disease. Use resistant hybrids. Rotate crops. Bury crop residue.",
        "preventive": ["Plant resistant hybrids", "Crop rotation", "Tillage to bury residue", "Avoid dense planting"],
        "severity_factors": {"wet_cool_weather": 1.5, "high_humidity": 1.3, "susceptible_hybrid": 1.4}
    },
    "Corn_(maize)___healthy": {
        "treatment": "No treatment needed. Your corn crop appears healthy! Maintain good agronomic practices.",
        "preventive": ["Balanced fertilization", "Adequate irrigation", "Weed control", "Regular scouting"],
        "severity_factors": {}
    },

    # Grape
    "Grape___Black_rot": {
        "treatment": "Apply Mancozeb or Captan fungicides starting at bud break through harvest. Remove mummified berries. Prune for air circulation.",
        "preventive": ["Sanitation (remove mummies)", "Fungicide program", "Canopy management", "Avoid overhead irrigation"],
        "severity_factors": {"wet_warm_weather": 1.5, "poor_sanitation": 1.4}
    },
    "Grape___Esca_(Black_Measles)": {
        "treatment": "No effective chemical treatment. Prune out infected wood during dormancy. Remove infected vines. Protect pruning wounds. Consider trunk renewal.",
        "preventive": ["Protect pruning wounds", "Avoid stress", "Trunk renewal on young vines", "Remove infected plants"],
        "severity_factors": {"vine_age": 1.3, "drought_stress": 1.2, "pruning_wounds": 1.4}
    },
    "Grape___Leaf_blight_(Isariopsis_Leaf_Spot)": {
        "treatment": "Apply copper-based fungicides or Mancozeb. Improve air circulation. Remove and destroy infected leaves. Apply fungicides every 10-14 days.",
        "preventive": ["Good canopy management", "Remove infected leaves", "Fungicide applications", "Avoid overhead irrigation"],
        "severity_factors": {"high_humidity": 1.4, "poor_air_circulation": 1.3}
    },
    "Grape___healthy": {
        "treatment": "No treatment needed. Your grape crop appears healthy! Continue vineyard management practices.",
        "preventive": ["Regular monitoring", "Canopy management", "Balanced nutrition", "Weed control"],
        "severity_factors": {}
    },

    # Orange/Citrus
    "Orange___Haunglongbing_(Citrus_greening)": {
        "treatment": "No cure available. Remove and destroy infected trees immediately. Control psyllid vectors with insecticides (Imidacloprid). Plant disease-free nursery stock only.",
        "preventive": ["Use certified disease-free plants", "Control Asian citrus psyllid", "Remove infected trees", "Monitor regularly"],
        "severity_factors": {"psyllid_presence": 1.8, "infected_neighbors": 1.6, "no_vector_control": 1.7}
    },

    # Peach
    "Peach___Bacterial_spot": {
        "treatment": "Apply copper-based bactericides. Use antibiotic sprays (Streptomycin if allowed). Plant resistant varieties. Reduce overhead irrigation.",
        "preventive": ["Plant resistant varieties", "Copper sprays in fall", "Avoid overhead irrigation", "Prune for air circulation"],
        "severity_factors": {"warm_wet_weather": 1.5, "overhead_irrigation": 1.3, "susceptible_variety": 1.4}
    },
    "Peach___healthy": {
        "treatment": "No treatment needed. Your peach crop appears healthy! Maintain orchard management.",
        "preventive": ["Regular pruning", "Balanced fertilization", "Pest monitoring", "Proper irrigation"],
        "severity_factors": {}
    },

    # Bell Pepper
    "Pepper,_bell___Bacterial_spot": {
        "treatment": "Apply copper-based bactericides plus Mancozeb. Rotate crops (3-4 years). Use pathogen-free seeds. Remove infected plants. Avoid overhead irrigation.",
        "preventive": ["Use disease-free seeds", "Crop rotation", "Avoid overhead watering", "Sanitation", "Plant resistant varieties"],
        "severity_factors": {"warm_wet_weather": 1.5, "overhead_irrigation": 1.4, "continuous_cropping": 1.5}
    },
    "Pepper,_bell___healthy": {
        "treatment": "No treatment needed. Your pepper crop appears healthy! Continue good management practices.",
        "preventive": ["Regular monitoring", "Balanced nutrition", "Proper spacing", "Weed control"],
        "severity_factors": {}
    },

    # Potato
    "Potato___Early_blight": {
        "treatment": "Apply fungicides like Chlorothalonil, Mancozeb, or Azoxystrobin every 7-10 days. Remove infected lower leaves. Rotate crops. Use certified seed.",
        "preventive": ["Crop rotation (3-4 years)", "Use certified seed", "Hill plants properly", "Destroy crop residue", "Fungicide program"],
        "severity_factors": {"warm_humid_weather": 1.4, "stressed_plants": 1.3, "poor_rotation": 1.5}
    },
    "Potato___Late_blight": {
        "treatment": "Apply fungicides immediately: Mancozeb, Chlorothalonil, or metalaxyl-M. Spray every 5-7 days during wet weather. Destroy infected plants. Avoid overhead irrigation.",
        "preventive": ["Use resistant varieties", "Certified disease-free seed", "Destroy cull piles", "Fungicide program", "Avoid wet conditions"],
        "severity_factors": {"cool_wet_weather": 1.8, "high_humidity": 1.6, "susceptible_variety": 1.5}
    },
    "Potato___healthy": {
        "treatment": "No treatment needed. Your potato crop appears healthy! Maintain good cultural practices.",
        "preventive": ["Proper hilling", "Balanced fertilization", "Weed control", "Regular monitoring"],
        "severity_factors": {}
    },

    # Raspberry
    "Raspberry___healthy": {
        "treatment": "No treatment needed. Your raspberry crop appears healthy! Continue cane management.",
        "preventive": ["Regular pruning", "Remove old canes", "Adequate spacing", "Proper irrigation"],
        "severity_factors": {}
    },

    # Soybean
    "Soybean___healthy": {
        "treatment": "No treatment needed. Your soybean crop appears healthy! Maintain field management.",
        "preventive": ["Crop rotation", "Balanced fertility", "Weed control", "Scout for pests"],
        "severity_factors": {}
    },

    # Squash
    "Squash___Powdery_mildew": {
        "treatment": "Apply sulfur-based fungicides or Myclobutanil every 7-10 days. Improve air circulation. Remove heavily infected leaves. Use resistant varieties.",
        "preventive": ["Plant resistant varieties", "Adequate spacing", "Avoid overhead irrigation", "Remove infected leaves"],
        "severity_factors": {"high_humidity": 1.4, "poor_air_flow": 1.3, "dense_planting": 1.3}
    },

    # Strawberry
    "Strawberry___Leaf_scorch": {
        "treatment": "Apply fungicides like Captan or copper-based products. Remove and destroy infected leaves. Renovate plants after harvest. Improve drainage.",
        "preventive": ["Plant resistant varieties", "Good air circulation", "Avoid overhead irrigation", "Remove old leaves", "Proper drainage"],
        "severity_factors": {"high_humidity": 1.3, "poor_drainage": 1.4, "dense_planting": 1.2}
    },
    "Strawberry___healthy": {
        "treatment": "No treatment needed. Your strawberry crop appears healthy! Continue bed management.",
        "preventive": ["Regular renovation", "Remove old leaves", "Adequate spacing", "Balanced nutrition"],
        "severity_factors": {}
    },

    # Tomato
    "Tomato___Bacterial_spot": {
        "treatment": "Apply copper-based bactericides. Use pathogen-free seeds and transplants. Rotate crops (3-4 years). Remove infected plants. Avoid overhead irrigation.",
        "preventive": ["Use disease-free seeds", "Crop rotation", "Avoid overhead watering", "Plant resistant varieties", "Sanitation"],
        "severity_factors": {"warm_wet_weather": 1.5, "overhead_irrigation": 1.4, "continuous_tomatoes": 1.5}
    },
    "Tomato___Early_blight": {
        "treatment": "Apply fungicides: Chlorothalonil, Mancozeb, or Azoxystrobin every 7-10 days. Remove lower infected leaves. Mulch plants. Stake for air circulation.",
        "preventive": ["Crop rotation", "Mulching", "Proper spacing", "Remove infected leaves", "Fungicide program"],
        "severity_factors": {"warm_humid_weather": 1.4, "poor_air_flow": 1.3, "stressed_plants": 1.3}
    },
    "Tomato___Late_blight": {
        "treatment": "Apply fungicides immediately: Mancozeb, Chlorothalonil, or Metalaxyl-M every 5-7 days in wet weather. Destroy infected plants. Remove volunteer tomatoes and potatoes.",
        "preventive": ["Use resistant varieties", "Destroy infected plants", "Avoid overhead irrigation", "Fungicide program", "Proper spacing"],
        "severity_factors": {"cool_wet_weather": 1.8, "high_humidity": 1.6, "susceptible_variety": 1.5}
    },
    "Tomato___Leaf_Mold": {
        "treatment": "Apply fungicides like Chlorothalonil or Mancozeb. Improve greenhouse ventilation. Reduce humidity. Remove infected leaves. Use resistant varieties.",
        "preventive": ["Use resistant varieties", "Improve air circulation", "Reduce humidity", "Avoid overhead watering"],
        "severity_factors": {"high_humidity": 1.6, "poor_ventilation": 1.5, "greenhouse": 1.4}
    },
    "Tomato___Septoria_leaf_spot": {
        "treatment": "Apply fungicides: Chlorothalonil, Mancozeb, or copper-based products every 7-10 days. Remove lower infected leaves. Mulch plants. Rotate crops.",
        "preventive": ["Crop rotation", "Mulching", "Remove infected leaves", "Avoid overhead irrigation", "Proper spacing"],
        "severity_factors": {"warm_wet_weather": 1.4, "overhead_irrigation": 1.3, "poor_rotation": 1.4}
    },
    "Tomato___Spider_mites Two-spotted_spider_mite": {
        "treatment": "Apply miticides like Abamectin or insecticidal soap. Spray with water to dislodge mites. Use predatory mites. Avoid excessive nitrogen. Maintain plant vigor.",
        "preventive": ["Monitor regularly", "Avoid water stress", "Use predatory mites", "Avoid excessive nitrogen", "Remove infested plants"],
        "severity_factors": {"hot_dry_weather": 1.5, "water_stress": 1.4, "dusty_conditions": 1.3}
    },
    "Tomato___Target_Spot": {
        "treatment": "Apply fungicides: Chlorothalonil, Mancozeb, or Azoxystrobin every 7-14 days. Improve air circulation. Remove infected leaves. Mulch plants.",
        "preventive": ["Proper spacing", "Mulching", "Remove infected leaves", "Crop rotation", "Fungicide program"],
        "severity_factors": {"warm_humid_weather": 1.4, "poor_air_flow": 1.3}
    },
    "Tomato___Tomato_Yellow_Leaf_Curl_Virus": {
        "treatment": "No cure. Remove and destroy infected plants immediately. Control whitefly vectors with insecticides (Imidacloprid, Thiamethoxam). Use reflective mulches. Plant resistant varieties.",
        "preventive": ["Use virus-resistant varieties", "Control whiteflies", "Use insect-proof nets", "Remove infected plants", "Reflective mulches"],
        "severity_factors": {"whitefly_population": 1.7, "no_vector_control": 1.6, "susceptible_variety": 1.5}
    },
    "Tomato___Tomato_mosaic_virus": {
        "treatment": "No cure. Remove and destroy infected plants. Disinfect tools and hands with bleach solution. Use virus-free seeds. Control aphid vectors if present.",
        "preventive": ["Use virus-free seeds", "Sanitize tools", "Avoid tobacco use near plants", "Remove infected plants", "Control aphids"],
        "severity_factors": {"contaminated_tools": 1.5, "infected_transplants": 1.6, "tobacco_contact": 1.4}
    },
    "Tomato___healthy": {
        "treatment": "No treatment needed. Your tomato crop appears healthy! Continue good management practices.",
        "preventive": ["Regular monitoring", "Balanced nutrition", "Proper spacing", "Weed control", "Crop rotation"],
        "severity_factors": {}
    },
}


# ============================================================================
# Helper Functions
# ============================================================================

def _get_treatment_recommendation(disease_class: str) -> Dict[str, Any]:
    """
    Get treatment recommendation for a disease class

    Args:
        disease_class: Disease class name (e.g., "Tomato___Late_blight")

    Returns:
        Dictionary with treatment, preventive measures, and severity factors
    """
    if disease_class in TREATMENT_RECOMMENDATIONS:
        return TREATMENT_RECOMMENDATIONS[disease_class]
    else:
        # Generic fallback for unknown diseases
        logger.warning(f"No specific treatment for {disease_class}, using generic advice")
        return {
            "treatment": (
                "Consult a local agricultural extension officer for specific treatment. "
                "General measures: Remove and destroy infected plant parts, improve air circulation, "
                "maintain plant vigor, and consider preventive fungicide applications."
            ),
            "preventive": [
                "Regular crop monitoring",
                "Good field sanitation",
                "Proper plant spacing",
                "Balanced fertilization",
                "Crop rotation"
            ],
            "severity_factors": {}
        }


def _estimate_severity(confidence: float, disease_class: str) -> str:
    """
    Estimate disease severity based on confidence and disease characteristics

    Args:
        confidence: Model confidence (0.0-1.0)
        disease_class: Disease class name

    Returns:
        Severity level: "mild", "moderate", or "severe"
    """
    # For healthy plants, no severity
    if "healthy" in disease_class.lower():
        return "none"

    # Base severity on confidence
    if confidence >= 0.90:
        base_severity = "severe"  # High confidence = clear symptoms
    elif confidence >= 0.75:
        base_severity = "moderate"
    else:
        base_severity = "mild"

    # Adjust based on disease characteristics
    treatment_info = TREATMENT_RECOMMENDATIONS.get(disease_class, {})
    severity_factors = treatment_info.get("severity_factors", {})

    # If disease has high-risk factors, bump up severity
    if severity_factors and base_severity == "mild":
        base_severity = "moderate"

    return base_severity


def _validate_crop_type_match(
    predicted_crop: str,
    user_hint: Optional[str]
) -> Dict[str, Any]:
    """
    Check if predicted crop matches user-provided hint

    Args:
        predicted_crop: Crop predicted by model (e.g., "Tomato")
        user_hint: Optional user-provided crop type

    Returns:
        Dictionary with match status and message
    """
    if not user_hint:
        return {
            "match": None,
            "message": "No crop type provided by user"
        }

    # Normalize both for comparison
    predicted_normalized = predicted_crop.lower().strip()
    hint_normalized = user_hint.lower().strip()

    # Direct match
    if predicted_normalized == hint_normalized:
        return {
            "match": True,
            "message": f"Crop type matches: {predicted_crop}"
        }

    # Partial match (e.g., "tomato" in "cherry tomato")
    if predicted_normalized in hint_normalized or hint_normalized in predicted_normalized:
        return {
            "match": True,
            "message": f"Crop type partially matches: {predicted_crop} ~ {user_hint}"
        }

    # No match
    return {
        "match": False,
        "message": (
            f"Warning: Model detected {predicted_crop}, but you mentioned {user_hint}. "
            f"The image may be mislabeled or the model prediction may be incorrect."
        )
    }


# ============================================================================
# Core Prediction Function (for direct use and testing)
# ============================================================================

def detect_disease_core(
    image_bytes: bytes,
    crop_type: Optional[str] = None,
    user_query: Optional[str] = None
) -> Dict[str, Any]:
    """
    Detect crop disease from image bytes and provide treatment recommendations

    This tool uses a TensorFlow/Keras CNN model trained on PlantVillage dataset
    to identify diseases across 38 classes covering 14 crop types.

    Args:
        image_bytes: Raw image data as bytes (JPEG, PNG, etc.)
        crop_type: Optional user-provided crop type hint for validation
        user_query: Optional user query text (for context, not currently used)

    Returns:
        Dictionary containing:
            - disease_name: Detected disease (e.g., "Late blight")
            - crop: Detected crop (e.g., "Tomato")
            - is_healthy: Boolean indicating if crop is healthy
            - confidence: Model confidence (0.0-1.0)
            - treatment: Recommended treatment measures
            - preventive_measures: List of preventive actions
            - severity: Estimated severity ("none", "mild", "moderate", "severe")
            - crop_type_match: Validation result if crop_type provided
            - parameters_used: Input parameters for debugging
            - error: Error message if detection failed (only present if error occurred)

    Example:
        >>> with open("tomato_leaf.jpg", "rb") as f:
        ...     image_bytes = f.read()
        >>> result = detect_disease_core(image_bytes, crop_type="tomato")
        >>> print(result["disease_name"])
        "Late blight"
        >>> print(result["treatment"][:50])
        "Apply fungicides immediately: Mancozeb, Chloroth..."
    """
    start_time = time.perf_counter()

    try:
        # Validate input
        if not image_bytes or len(image_bytes) == 0:
            error_msg = "Empty image data provided"
            logger.warning(error_msg)
            return {
                "error": error_msg,
                "parameters_used": {
                    "image_size_bytes": 0,
                    "crop_type_hint": crop_type,
                    "has_user_query": user_query is not None
                }
            }

        # Get disease detector instance
        detector = get_crop_disease_detector()

        # Check if model is loaded
        if detector.model is None:
            error_msg = "Disease detection model not loaded. Please check model file."
            logger.error(error_msg)
            return {
                "error": error_msg,
                "parameters_used": {
                    "image_size_bytes": len(image_bytes),
                    "crop_type_hint": crop_type,
                    "has_user_query": user_query is not None
                }
            }

        # Predict disease
        prediction_result = detector.predict_disease(image_bytes)

        # Check for prediction errors
        if not prediction_result.get("success"):
            error_msg = prediction_result.get("error", "Unknown prediction error")
            logger.warning(f"Prediction failed: {error_msg}")
            return {
                "error": error_msg,
                "parameters_used": {
                    "image_size_bytes": len(image_bytes),
                    "crop_type_hint": crop_type,
                    "has_user_query": user_query is not None
                }
            }

        # Extract prediction details
        prediction = prediction_result["prediction"]
        disease_class = prediction["class"]
        crop = prediction["crop"]
        disease = prediction["disease"]
        is_healthy = prediction["is_healthy"]
        confidence = prediction["confidence"]
        confidence_pct = prediction["confidence_percentage"]

        # Check confidence threshold (70%)
        if confidence < 0.70:
            logger.warning(
                f"Low confidence prediction: {disease_class} "
                f"({confidence_pct}%) < 70% threshold"
            )
            return {
                "error": (
                    f"Low confidence detection ({confidence_pct}%). "
                    f"Please provide a clearer image with better lighting and focus on the affected area. "
                    f"Detected: {disease} on {crop} (confidence: {confidence_pct}%)"
                ),
                "disease_name": disease,
                "crop": crop,
                "confidence": confidence,
                "confidence_percentage": confidence_pct,
                "threshold_required": 70.0,
                "parameters_used": {
                    "image_size_bytes": len(image_bytes),
                    "crop_type_hint": crop_type,
                    "has_user_query": user_query is not None
                }
            }

        # Get treatment recommendation
        treatment_info = _get_treatment_recommendation(disease_class)

        # Estimate severity
        severity = _estimate_severity(confidence, disease_class)

        # Validate crop type if provided
        crop_match = _validate_crop_type_match(crop, crop_type)

        # Calculate latency
        latency_ms = (time.perf_counter() - start_time) * 1000

        # Build result
        result = {
            "disease_name": disease,
            "crop": crop,
            "is_healthy": is_healthy,
            "confidence": confidence,
            "confidence_percentage": confidence_pct,
            "treatment": treatment_info["treatment"],
            "preventive_measures": treatment_info["preventive"],
            "severity": severity,
            "crop_type_match": crop_match,
            "parameters_used": {
                "image_size_bytes": len(image_bytes),
                "crop_type_hint": crop_type,
                "has_user_query": user_query is not None,
                "predicted_class": disease_class,
                "latency_ms": round(latency_ms, 2)
            }
        }

        logger.info(
            f"Disease detection: {crop} - {disease} "
            f"(confidence: {confidence_pct}%, severity: {severity}, "
            f"latency: {latency_ms:.0f}ms)"
        )

        return result

    except Exception as e:
        error_msg = f"Disease detection failed: {str(e)}"
        logger.error(error_msg, exc_info=True)
        return {
            "error": error_msg,
            "parameters_used": {
                "image_size_bytes": len(image_bytes) if image_bytes else 0,
                "crop_type_hint": crop_type,
                "has_user_query": user_query is not None
            }
        }


# ============================================================================
# Helper Functions for Direct Use (non-LangChain)
# ============================================================================

def get_supported_crops() -> list[str]:
    """Get list of supported crop types"""
    crops = set()
    for disease_class in TREATMENT_RECOMMENDATIONS.keys():
        crop = disease_class.split("___")[0].replace("_", " ")
        crops.add(crop)
    return sorted(list(crops))


def get_disease_classes() -> list[str]:
    """Get list of all 38 disease classes"""
    return sorted(list(TREATMENT_RECOMMENDATIONS.keys()))


def get_healthy_classes() -> list[str]:
    """Get list of healthy crop classes"""
    return [cls for cls in TREATMENT_RECOMMENDATIONS.keys() if "healthy" in cls.lower()]


# ============================================================================
# LangChain Tool Wrapper
# ============================================================================

@tool
def detect_disease(
    image_bytes: bytes,
    crop_type: Optional[str] = None,
    user_query: Optional[str] = None
) -> Dict[str, Any]:
    """
    Detect crop disease from image bytes and provide treatment recommendations

    This tool uses a TensorFlow/Keras CNN model trained on PlantVillage dataset
    to identify diseases across 38 classes covering 14 crop types.

    Args:
        image_bytes: Raw image data as bytes (JPEG, PNG, etc.)
        crop_type: Optional user-provided crop type hint for validation
        user_query: Optional user query text (for context)

    Returns:
        Dictionary containing disease detection results and treatment
    """
    return detect_disease_core(
        image_bytes=image_bytes,
        crop_type=crop_type,
        user_query=user_query
    )
