"""
Regional Climate Database for India

Provides climate parameters for major Indian cities and agricultural regions.
Used by agents to infer climate when user mentions location.

BUG FIX #3: Enables location-based crop recommendations
"""

from typing import Dict, Any, Optional

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


def infer_soil_from_region(location: str) -> Optional[str]:
    """
    Infer dominant soil type from region (rough approximation)

    Args:
        location: City, state, or region name

    Returns:
        Soil type (black/red/alluvial/sandy/loamy) or None

    Note: This is a rough approximation. Real soil varies widely.
    """
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

    # Sandy soil - Coastal, deserts
    sandy_regions = [
        "rajasthan", "gujarat coast", "coastal", "konkan",
        "jaipur", "jodhpur"
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
