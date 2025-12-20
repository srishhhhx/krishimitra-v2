"""
Fertilizer Recommendation Tool

This module provides a LangChain tool that wraps the XGBoost fertilizer
prediction model for use in the multi-agent system.
"""
from typing import Dict, Any, Optional
from pathlib import Path
import numpy as np
import joblib
from langchain.tools import tool

from core.logging import get_logger

logger = get_logger(__name__)

# ============================================================================
# Encoding Mappings (verified - see tools/ENCODINGS.md)
# ============================================================================

SOIL_TYPE_ENCODING = {
    "sandy": 0,
    "loamy": 1,
    "black": 2,
    "red": 3,
    "clayey": 4
}

CROP_TYPE_ENCODING = {
    "maize": 0,
    "sugarcane": 1,
    "cotton": 2,
    "tobacco": 3,
    "paddy": 4,
    "rice": 4,  # Alias for paddy
    "barley": 5,
    "wheat": 6,
    "millets": 7,
    "oil seeds": 8,
    "oilseeds": 8,  # Alias for oil seeds
    "pulses": 9,
    "ground nuts": 10,
    "groundnuts": 10  # Alias for ground nuts
}

NPK_RATIOS = {
    "Urea": "46-0-0",
    "DAP": "18-46-0",
    "14-35-14": "14-35-14",
    "28-28": "28-28-0",
    "17-17-17": "17-17-17",
    "20-20": "20-20-0",
    "10-26-26": "10-26-26"
}

# ============================================================================
# Model Loading (singleton pattern)
# ============================================================================

_xgb_model = None
_fert_dict = None


def _load_models() -> tuple[Any, Dict[int, str]]:
    """
    Load XGBoost model and fertilizer dictionary (lazy loading)

    Returns:
        Tuple of (xgb_model, fertilizer_dict)

    Raises:
        Exception: If models cannot be loaded
    """
    global _xgb_model, _fert_dict

    if _xgb_model is None or _fert_dict is None:
        try:
            backend_dir = Path(__file__).parent.parent
            model_path = backend_dir / "models" / "xgb_pipeline.joblib"
            dict_path = backend_dir / "models" / "fertname_dict.joblib"

            _xgb_model = joblib.load(model_path)
            _fert_dict = joblib.load(dict_path)

            logger.info("✅ Fertilizer models loaded successfully")
            logger.info(f"Fertilizer options: {_fert_dict}")

        except Exception as e:
            logger.error(f"Failed to load fertilizer models: {e}", exc_info=True)
            raise

    return _xgb_model, _fert_dict


def _normalize_string(s: str) -> str:
    """
    Normalize string input (lowercase, strip whitespace)

    Args:
        s: Input string

    Returns:
        Normalized string
    """
    return s.lower().strip()


def _generate_reasoning(
    fertilizer_name: str,
    npk_ratio: str,
    soil_type: str,
    crop_type: str,
    nitrogen: float,
    phosphorous: float,
    potassium: float,
    temperature: float,
    humidity: float,
    moisture: float
) -> str:
    """
    Generate human-readable reasoning for the fertilizer recommendation

    Args:
        fertilizer_name: Recommended fertilizer
        npk_ratio: NPK ratio of the fertilizer
        soil_type: Input soil type
        crop_type: Input crop type
        nitrogen: Soil nitrogen content
        phosphorous: Soil phosphorous content
        potassium: Soil potassium content
        temperature: Temperature
        humidity: Humidity
        moisture: Soil moisture

    Returns:
        Human-readable reasoning string
    """
    reasoning_parts = [
        f"Based on your {soil_type} soil and {crop_type} crop, "
        f"the recommended fertilizer is {fertilizer_name} (NPK ratio: {npk_ratio})."
    ]

    # Nutrient analysis
    if nitrogen < 40:
        reasoning_parts.append(f"Your soil has low nitrogen ({nitrogen} kg/ha).")
    elif nitrogen > 80:
        reasoning_parts.append(f"Your soil has high nitrogen ({nitrogen} kg/ha).")

    if phosphorous < 30:
        reasoning_parts.append(f"Phosphorous is low ({phosphorous} kg/ha).")
    elif phosphorous > 60:
        reasoning_parts.append(f"Phosphorous is high ({phosphorous} kg/ha).")

    if potassium < 30:
        reasoning_parts.append(f"Potassium is low ({potassium} kg/ha).")
    elif potassium > 60:
        reasoning_parts.append(f"Potassium is high ({potassium} kg/ha).")

    # Environmental conditions
    if temperature < 20:
        reasoning_parts.append(f"Temperature is cool ({temperature}°C).")
    elif temperature > 35:
        reasoning_parts.append(f"Temperature is warm ({temperature}°C).")

    if humidity < 50:
        reasoning_parts.append(f"Humidity is low ({humidity}%).")
    elif humidity > 75:
        reasoning_parts.append(f"Humidity is high ({humidity}%).")

    if moisture < 40:
        reasoning_parts.append(f"Soil moisture is low ({moisture}%).")
    elif moisture > 65:
        reasoning_parts.append(f"Soil moisture is high ({moisture}%).")

    # Fertilizer-specific guidance
    if fertilizer_name == "Urea":
        reasoning_parts.append(
            "Urea is a high-nitrogen fertilizer (46-0-0) ideal for rapid vegetative growth. "
            "Apply in split doses for best results."
        )
    elif fertilizer_name == "DAP":
        reasoning_parts.append(
            "DAP (Diammonium Phosphate) provides high phosphorus (18-46-0), "
            "essential for root development and flowering."
        )
    elif "17-17-17" in fertilizer_name:
        reasoning_parts.append(
            "This balanced fertilizer (17-17-17) provides equal nutrients for overall plant health."
        )
    elif "28-28" in fertilizer_name:
        reasoning_parts.append(
            "This balanced N-P fertilizer (28-28-0) supports both vegetative growth and flowering."
        )
    elif "10-26-26" in fertilizer_name:
        reasoning_parts.append(
            "This high P-K fertilizer (10-26-26) is excellent for fruiting and root crops."
        )

    return " ".join(reasoning_parts)


# ============================================================================
# Core Prediction Function (for direct use and testing)
# ============================================================================

def predict_fertilizer_core(
    temperature: float,
    humidity: float,
    moisture: float,
    soil_type: str,
    crop_type: str,
    nitrogen: float,
    phosphorous: float,
    potassium: float
) -> Dict[str, Any]:
    """
    Predict optimal fertilizer recommendation based on soil, crop, and environmental conditions.

    This tool uses an XGBoost model trained on agricultural data to recommend
    the most suitable fertilizer for given conditions.

    Args:
        temperature: Temperature in Celsius (10-50°C typical range)
        humidity: Relative humidity percentage (0-100%)
        moisture: Soil moisture percentage (0-100%)
        soil_type: Soil type - must be one of: sandy, loamy, black, red, clayey
        crop_type: Crop name - must be one of: maize, sugarcane, cotton, tobacco,
                   paddy/rice, barley, wheat, millets, oil seeds/oilseeds,
                   pulses, ground nuts/groundnuts
        nitrogen: Soil nitrogen content in kg/ha (0-200 typical)
        phosphorous: Soil phosphorous content in kg/ha (0-150 typical)
        potassium: Soil potassium content in kg/ha (0-150 typical)

    Returns:
        Dictionary containing:
            - fertilizer_name: Recommended fertilizer (e.g., "Urea", "DAP", "14-35-14")
            - npk_ratio: NPK ratio of the fertilizer (e.g., "46-0-0")
            - reasoning: Human-readable explanation for the recommendation
            - parameters_used: Dictionary of input parameters used
            - error: Error message if prediction failed (only present if error occurred)

    Example:
        >>> result = predict_fertilizer(
        ...     temperature=25.0,
        ...     humidity=60.0,
        ...     moisture=45.0,
        ...     soil_type="sandy",
        ...     crop_type="wheat",
        ...     nitrogen=40.0,
        ...     phosphorous=50.0,
        ...     potassium=30.0
        ... )
        >>> print(result["fertilizer_name"])
        "Urea"
        >>> print(result["npk_ratio"])
        "46-0-0"
    """
    try:
        # Normalize string inputs
        soil_type_normalized = _normalize_string(soil_type)
        crop_type_normalized = _normalize_string(crop_type)

        # Validate soil type
        if soil_type_normalized not in SOIL_TYPE_ENCODING:
            valid_soils = ", ".join(sorted(SOIL_TYPE_ENCODING.keys()))
            error_msg = f"Invalid soil_type '{soil_type}'. Must be one of: {valid_soils}"
            logger.warning(error_msg)
            return {
                "error": error_msg,
                "valid_soil_types": list(SOIL_TYPE_ENCODING.keys()),
                "parameters_used": {
                    "soil_type": soil_type,
                    "crop_type": crop_type,
                    "temperature": temperature,
                    "humidity": humidity,
                    "moisture": moisture,
                    "nitrogen": nitrogen,
                    "phosphorous": phosphorous,
                    "potassium": potassium
                }
            }

        # Validate crop type
        if crop_type_normalized not in CROP_TYPE_ENCODING:
            valid_crops = ", ".join(sorted(set(CROP_TYPE_ENCODING.keys())))
            error_msg = f"Invalid crop_type '{crop_type}'. Must be one of: {valid_crops}"
            logger.warning(error_msg)
            return {
                "error": error_msg,
                "valid_crop_types": list(set(CROP_TYPE_ENCODING.keys())),
                "parameters_used": {
                    "soil_type": soil_type,
                    "crop_type": crop_type,
                    "temperature": temperature,
                    "humidity": humidity,
                    "moisture": moisture,
                    "nitrogen": nitrogen,
                    "phosphorous": phosphorous,
                    "potassium": potassium
                }
            }

        # Load models
        xgb_model, fert_dict = _load_models()

        # Encode categorical variables
        soil_encoded = SOIL_TYPE_ENCODING[soil_type_normalized]
        crop_encoded = CROP_TYPE_ENCODING[crop_type_normalized]

        # Create input array in correct order
        # [Temperature, Humidity, Moisture, SoilType, CropType, N, P, K]
        input_array = np.array([[
            temperature,
            humidity,
            moisture,
            soil_encoded,
            crop_encoded,
            nitrogen,
            phosphorous,
            potassium
        ]])

        # Predict
        prediction_code = xgb_model.predict(input_array)[0]
        fertilizer_name = fert_dict.get(prediction_code, "Unknown")
        npk_ratio = NPK_RATIOS.get(fertilizer_name, "Unknown")

        # Generate reasoning
        reasoning = _generate_reasoning(
            fertilizer_name=fertilizer_name,
            npk_ratio=npk_ratio,
            soil_type=soil_type_normalized,
            crop_type=crop_type_normalized,
            nitrogen=nitrogen,
            phosphorous=phosphorous,
            potassium=potassium,
            temperature=temperature,
            humidity=humidity,
            moisture=moisture
        )

        result = {
            "fertilizer_name": fertilizer_name,
            "npk_ratio": npk_ratio,
            "reasoning": reasoning,
            "parameters_used": {
                "soil_type": soil_type_normalized,
                "crop_type": crop_type_normalized,
                "temperature": temperature,
                "humidity": humidity,
                "moisture": moisture,
                "nitrogen": nitrogen,
                "phosphorous": phosphorous,
                "potassium": potassium,
                "soil_type_code": int(soil_encoded),
                "crop_type_code": int(crop_encoded)
            }
        }

        logger.info(
            f"Fertilizer prediction: {fertilizer_name} "
            f"(soil={soil_type_normalized}, crop={crop_type_normalized})"
        )

        return result

    except Exception as e:
        error_msg = f"Fertilizer prediction failed: {str(e)}"
        logger.error(error_msg, exc_info=True)
        return {
            "error": error_msg,
            "parameters_used": {
                "soil_type": soil_type,
                "crop_type": crop_type,
                "temperature": temperature,
                "humidity": humidity,
                "moisture": moisture,
                "nitrogen": nitrogen,
                "phosphorous": phosphorous,
                "potassium": potassium
            }
        }


# ============================================================================
# Helper Functions for Direct Use (non-LangChain)
# ============================================================================

def get_valid_soil_types() -> list[str]:
    """Get list of valid soil type strings"""
    return list(SOIL_TYPE_ENCODING.keys())


def get_valid_crop_types() -> list[str]:
    """Get list of valid crop type strings (including aliases)"""
    return list(set(CROP_TYPE_ENCODING.keys()))


def get_fertilizer_options() -> list[str]:
    """Get list of possible fertilizer outputs"""
    _, fert_dict = _load_models()
    return list(set(fert_dict.values()))


# ============================================================================
# LangChain Tool Wrapper
# ============================================================================

@tool
def predict_fertilizer(
    temperature: float,
    humidity: float,
    moisture: float,
    soil_type: str,
    crop_type: str,
    nitrogen: float,
    phosphorous: float,
    potassium: float
) -> Dict[str, Any]:
    """
    Predict optimal fertilizer recommendation based on soil, crop, and environmental conditions.

    This tool uses an XGBoost model trained on agricultural data to recommend
    the most suitable fertilizer for given conditions.

    Args:
        temperature: Temperature in Celsius (10-50°C typical range)
        humidity: Relative humidity percentage (0-100%)
        moisture: Soil moisture percentage (0-100%)
        soil_type: Soil type - must be one of: sandy, loamy, black, red, clayey
        crop_type: Crop name - must be one of: maize, sugarcane, cotton, tobacco,
                   paddy/rice, barley, wheat, millets, oil seeds/oilseeds,
                   pulses, ground nuts/groundnuts
        nitrogen: Soil nitrogen content in kg/ha (0-200 typical)
        phosphorous: Soil phosphorous content in kg/ha (0-150 typical)
        potassium: Soil potassium content in kg/ha (0-150 typical)

    Returns:
        Dictionary containing fertilizer recommendation and reasoning
    """
    return predict_fertilizer_core(
        temperature=temperature,
        humidity=humidity,
        moisture=moisture,
        soil_type=soil_type,
        crop_type=crop_type,
        nitrogen=nitrogen,
        phosphorous=phosphorous,
        potassium=potassium
    )
