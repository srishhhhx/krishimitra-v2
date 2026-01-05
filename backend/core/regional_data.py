"""
Regional Climate and Soil Database for India

Provides climate and soil parameters for major Indian cities and agricultural regions.
Used by agents to infer parameters when user mentions location.

BUG FIX #3: Enables location-based crop recommendations
"""

import json
import os
from typing import Dict, Any, Optional

from core.logging import get_logger

logger = get_logger(__name__)

# Load soil data from JSON file
_SOIL_DATA_PATH = os.path.join(os.path.dirname(__file__), "..", "data", "regional_soil_data.json")
_SOIL_DATA: Dict[str, Any] = {}

def _load_soil_data():
    """Load soil data from JSON file (lazy loading)"""
    global _SOIL_DATA
    if _SOIL_DATA:
        return  # Already loaded
    
    try:
        with open(_SOIL_DATA_PATH, 'r') as f:
            _SOIL_DATA = json.load(f)
            logger.info(f"Loaded regional soil data from {_SOIL_DATA_PATH}")
    except FileNotFoundError:
        logger.warning(f"Soil data file not found: {_SOIL_DATA_PATH}")
        _SOIL_DATA = {"regions": {}}
    except json.JSONDecodeError as e:
        logger.error(f"Failed to parse soil data JSON: {e}")
        _SOIL_DATA = {"regions": {}}


# Regional climate data (representative values for crop recommendation)
# Values: temperature (°C), humidity (%), rainfall (mm/month)
REGIONAL_CLIMATE = {
    # Major Cities - South India
    "Bangalore": {"temperature": 25, "humidity": 65, "rainfall": 100},
    "Bengaluru": {"temperature": 25, "humidity": 65, "rainfall": 100},
    "Chennai": {"temperature": 30, "humidity": 75, "rainfall": 120},
    "Hyderabad": {"temperature": 28, "humidity": 55, "rainfall": 80},
    "Mysore": {"temperature": 24, "humidity": 70, "rainfall": 90},
    "Coimbatore": {"temperature": 28, "humidity": 65, "rainfall": 70},
    "Madurai": {"temperature": 29, "humidity": 60, "rainfall": 85},

    # Major Cities - West India
    "Mumbai": {"temperature": 27, "humidity": 75, "rainfall": 200},
    "Pune": {"temperature": 25, "humidity": 60, "rainfall": 70},
    "Ahmedabad": {"temperature": 28, "humidity": 50, "rainfall": 80},
    "Surat": {"temperature": 27, "humidity": 70, "rainfall": 120},
    "Nagpur": {"temperature": 28, "humidity": 55, "rainfall": 120},
    "Nashik": {"temperature": 25, "humidity": 60, "rainfall": 60},

    # Major Cities - North India
    "Delhi": {"temperature": 25, "humidity": 60, "rainfall": 65},
    "Jaipur": {"temperature": 26, "humidity": 50, "rainfall": 65},
    "Lucknow": {"temperature": 25, "humidity": 65, "rainfall": 100},
    "Kanpur": {"temperature": 26, "humidity": 60, "rainfall": 85},
    "Agra": {"temperature": 25, "humidity": 60, "rainfall": 70},
    "Meerut": {"temperature": 24, "humidity": 65, "rainfall": 80},
    "Varanasi": {"temperature": 26, "humidity": 70, "rainfall": 100},
    "Patna": {"temperature": 26, "humidity": 70, "rainfall": 120},

    # Major Cities - East India
    "Kolkata": {"temperature": 27, "humidity": 75, "rainfall": 150},
    "Bhubaneswar": {"temperature": 28, "humidity": 75, "rainfall": 140},
    "Ranchi": {"temperature": 24, "humidity": 65, "rainfall": 130},

    # States (average across state)
    "Maharashtra": {"temperature": 26, "humidity": 65, "rainfall": 100},
    "Karnataka": {"temperature": 25, "humidity": 65, "rainfall": 90},
    "Kerala": {"temperature": 27, "humidity": 80, "rainfall": 280},
    "Tamil Nadu": {"temperature": 29, "humidity": 70, "rainfall": 100},
    "Telangana": {"temperature": 28, "humidity": 55, "rainfall": 85},
    "Andhra Pradesh": {"temperature": 29, "humidity": 60, "rainfall": 90},
    "Gujarat": {"temperature": 27, "humidity": 55, "rainfall": 80},
    "Rajasthan": {"temperature": 27, "humidity": 40, "rainfall": 55},
    "Punjab": {"temperature": 24, "humidity": 60, "rainfall": 65},
    "Haryana": {"temperature": 25, "humidity": 55, "rainfall": 60},
    "Uttar Pradesh": {"temperature": 25, "humidity": 65, "rainfall": 90},
    "Madhya Pradesh": {"temperature": 26, "humidity": 60, "rainfall": 110},
    "West Bengal": {"temperature": 27, "humidity": 75, "rainfall": 150},
    "Bihar": {"temperature": 26, "humidity": 70, "rainfall": 115},
    "Odisha": {"temperature": 28, "humidity": 75, "rainfall": 140},

    # Agricultural Regions
    "Vidarbha": {"temperature": 28, "humidity": 55, "rainfall": 100},  # Cotton belt
    "Marathwada": {"temperature": 27, "humidity": 50, "rainfall": 70},  # Sugarcane region
    "Western Maharashtra": {"temperature": 26, "humidity": 60, "rainfall": 75},
    "Konkan": {"temperature": 27, "humidity": 80, "rainfall": 250},  # Coastal, high rainfall
    "Malnad": {"temperature": 23, "humidity": 75, "rainfall": 200},  # Karnataka hill region
    "Coastal Karnataka": {"temperature": 27, "humidity": 80, "rainfall": 220},
    "Deccan": {"temperature": 26, "humidity": 55, "rainfall": 80},  # Plateau region
    "Bundelkhand": {"temperature": 26, "humidity": 55, "rainfall": 80},  # UP/MP region
    
    # Common spelling variations and old names (ROBUSTNESS FIX)
    "Maharastra": {"temperature": 26, "humidity": 65, "rainfall": 100},  # Common typo
    "Banglore": {"temperature": 25, "humidity": 65, "rainfall": 100},  # Common typo
    "Bombay": {"temperature": 27, "humidity": 75, "rainfall": 200},  # Old name
    "Calcutta": {"temperature": 27, "humidity": 75, "rainfall": 150},  # Old name
    "Madras": {"temperature": 30, "humidity": 75, "rainfall": 120},  # Old name
    "Tamilnadu": {"temperature": 29, "humidity": 70, "rainfall": 100},
    
    # Northeast States (CRITICAL - previously missing)
    "Meghalaya": {"temperature": 22, "humidity": 85, "rainfall": 250},  # Wettest region
    "Shillong": {"temperature": 20, "humidity": 85, "rainfall": 250},
    "Nagaland": {"temperature": 21, "humidity": 75, "rainfall": 180},
    "Kohima": {"temperature": 18, "humidity": 75, "rainfall": 180},
    "Dimapur": {"temperature": 25, "humidity": 80, "rainfall": 200},
    "Mizoram": {"temperature": 22, "humidity": 80, "rainfall": 220},
    "Aizawl": {"temperature": 22, "humidity": 80, "rainfall": 220},
    "Manipur": {"temperature": 21, "humidity": 75, "rainfall": 160},
    "Imphal": {"temperature": 21, "humidity": 75, "rainfall": 160},
    "Tripura": {"temperature": 26, "humidity": 80, "rainfall": 200},
    "Agartala": {"temperature": 26, "humidity": 80, "rainfall": 200},
    "Arunachal Pradesh": {"temperature": 18, "humidity": 75, "rainfall": 280},
    "Arunachalpradesh": {"temperature": 18, "humidity": 75, "rainfall": 280},
    "Itanagar": {"temperature": 22, "humidity": 78, "rainfall": 280},
    "Sikkim": {"temperature": 16, "humidity": 80, "rainfall": 300},
    "Gangtok": {"temperature": 16, "humidity": 80, "rainfall": 300},
    "Guwahati": {"temperature": 25, "humidity": 80, "rainfall": 180},
    
    # Hill States
    "Uttarakhand": {"temperature": 20, "humidity": 60, "rainfall": 150},
    "Dehradun": {"temperature": 22, "humidity": 65, "rainfall": 180},
    "Himachal Pradesh": {"temperature": 18, "humidity": 55, "rainfall": 120},
    "Himachalpradesh": {"temperature": 18, "humidity": 55, "rainfall": 120},
    "Shimla": {"temperature": 15, "humidity": 60, "rainfall": 150},
    "Jammu and Kashmir": {"temperature": 16, "humidity": 55, "rainfall": 100},
    "Jammu": {"temperature": 24, "humidity": 55, "rainfall": 100},
    "Srinagar": {"temperature": 14, "humidity": 60, "rainfall": 70},
    "Ladakh": {"temperature": 10, "humidity": 30, "rainfall": 20},
    "Leh": {"temperature": 10, "humidity": 30, "rainfall": 20},
}


def get_climate_for_location(location: str) -> Optional[Dict[str, float]]:
    """
    Get climate parameters for a location

    Args:
        location: City, state, or region name

    Returns:
        Dict with temperature, humidity, rainfall, or None if not found

    Example:
        >>> climate = get_climate_for_location("Bangalore")
        >>> climate
        {'temperature': 25, 'humidity': 65, 'rainfall': 100}
    """
    if not location:
        return None

    # Case-insensitive lookup
    location_title = location.title()  # "bangalore" → "Bangalore"

    return REGIONAL_CLIMATE.get(location_title)


def get_soil_for_location(location: str) -> Optional[Dict[str, Any]]:
    """
    Get soil characteristics for a location from JSON database
    
    Args:
        location: City, district, or state name
        
    Returns:
        Dict with soil_type, N, P, K, ph or None if not found
        
    Example:
        >>> soil = get_soil_for_location("Pune")
        >>> soil
        {'soil_type': 'black', 'N': 55, 'P': 38, 'K': 70, 'ph': 7.3}
    """
    _load_soil_data()
    
    if not location or not _SOIL_DATA.get("regions"):
        return None
    
    location_lower = location.lower().strip()
    
    # Search through all state regions
    for state_name, districts in _SOIL_DATA["regions"].items():
        if isinstance(districts, dict):
            # Direct district lookup
            if location_lower in districts:
                soil_info = districts[location_lower]
                logger.info(f"Soil data found for {location}: {soil_info}")
                return soil_info
    
    # Try fuzzy matching (partial match)
    for state_name, districts in _SOIL_DATA["regions"].items():
        if isinstance(districts, dict):
            for district_name, soil_info in districts.items():
                if location_lower in district_name or district_name in location_lower:
                    logger.info(f"Soil data fuzzy matched {location} → {district_name}: {soil_info}")
                    return soil_info
    
    logger.warning(f"No soil data found for location: {location}")
    return None


def get_regional_data(location: str) -> Dict[str, Any]:
    """
    Get complete regional data (climate + soil) for a location
    
    This is the unified function for agents to get all location-based parameters.
    
    Args:
        location: City, district, or state name
        
    Returns:
        Dict with climate and soil data (may have None values if not found)
        
    Example:
        >>> data = get_regional_data("Pune")
        >>> data
        {
            'climate': {'temperature': 25, 'humidity': 60, 'rainfall': 70},
            'soil': {'soil_type': 'black', 'N': 55, 'P': 38, 'K': 70, 'ph': 7.3},
            'location_found': True
        }
    """
    climate = get_climate_for_location(location)
    soil = get_soil_for_location(location)
    
    return {
        "climate": climate,
        "soil": soil,
        "location_found": climate is not None or soil is not None
    }


def infer_soil_from_region(location: str) -> Optional[str]:
    """
    Infer dominant soil type from region
    
    DEPRECATED: Use get_soil_for_location() for complete soil info
    
    Args:
        location: City, state, or region name

    Returns:
        Soil type (black/red/alluvial/sandy/laterite) or None
    """
    soil_info = get_soil_for_location(location)
    if soil_info:
        return soil_info.get("soil_type")
    
    # Fallback to hardcoded logic for regions not in JSON
    location_lower = location.lower()

    # Black soil (Regur) - Deccan plateau, Maharashtra, Gujarat, MP
    black_soil_regions = [
        "vidarbha", "marathwada", "maharashtra", "gujarat",
        "madhya pradesh", "nagpur", "pune", "nashik", "ahmedabad"
    ]

    # Red soil - South India
    red_soil_regions = [
        "tamil nadu", "karnataka", "andhra pradesh", "telangana",
        "bangalore", "hyderabad", "chennai", "mysore", "coimbatore"
    ]

    # Alluvial soil - North India, river valleys
    alluvial_regions = [
        "punjab", "haryana", "uttar pradesh", "bihar", "west bengal",
        "delhi", "lucknow", "patna", "kolkata", "kanpur"
    ]

    # Sandy soil - deserts
    sandy_regions = [
        "rajasthan", "jaipur", "jodhpur", "bikaner"
    ]

    if any(region in location_lower for region in black_soil_regions):
        return "black"
    elif any(region in location_lower for region in red_soil_regions):
        return "red"
    elif any(region in location_lower for region in alluvial_regions):
        return "alluvial"
    elif any(region in location_lower for region in sandy_regions):
        return "sandy"

    return None  # Unknown region

