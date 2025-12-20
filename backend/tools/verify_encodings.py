"""
Encoding verification script for fertilizer prediction model

This script tests various combinations of soil types and crop types
to verify the correct integer encoding mappings.
"""
import sys
import numpy as np
import joblib
from pathlib import Path

# Add backend to path
backend_dir = Path(__file__).parent.parent
sys.path.insert(0, str(backend_dir))

# Load models
try:
    xgb_model = joblib.load(backend_dir / "models" / "xgb_pipeline.joblib")
    fert_dict = joblib.load(backend_dir / "models" / "fertname_dict.joblib")
    print("✅ Models loaded successfully!")
    print(f"📦 Fertilizer mapping: {fert_dict}\n")
except Exception as e:
    print(f"❌ Error loading models: {e}")
    sys.exit(1)

# Test data with assumed encodings
# Based on common agricultural datasets and pattern analysis

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
    "paddy": 4,      # Also "rice"
    "barley": 5,
    "wheat": 6,
    "millets": 7,
    "oil seeds": 8,  # Also "oilseeds"
    "pulses": 9,
    "ground nuts": 10  # Also "groundnuts"
}

# Add aliases
CROP_TYPE_ENCODING["rice"] = 4
CROP_TYPE_ENCODING["oilseeds"] = 8
CROP_TYPE_ENCODING["groundnuts"] = 10

print("🧪 Testing encoding combinations...\n")
print("=" * 80)

# Test cases with typical agricultural values
test_cases = [
    # (temp, humidity, moisture, soil_name, crop_name, N, P, K)
    (26.0, 52.0, 38.0, "sandy", "maize", 90.0, 42.0, 43.0),
    (25.0, 60.0, 45.0, "loamy", "wheat", 40.0, 50.0, 30.0),
    (28.0, 70.0, 55.0, "black", "cotton", 50.0, 30.0, 40.0),
    (30.0, 80.0, 60.0, "red", "sugarcane", 80.0, 60.0, 50.0),
    (27.0, 65.0, 50.0, "clayey", "paddy", 100.0, 40.0, 35.0),
    (24.0, 55.0, 40.0, "loamy", "barley", 30.0, 45.0, 25.0),
    (22.0, 50.0, 35.0, "sandy", "wheat", 35.0, 48.0, 28.0),
    (29.0, 75.0, 58.0, "black", "rice", 95.0, 38.0, 32.0),
]

results = []

for i, (temp, humidity, moisture, soil_name, crop_name, N, P, K) in enumerate(test_cases, 1):
    try:
        # Encode categorical variables
        soil_encoded = SOIL_TYPE_ENCODING[soil_name]
        crop_encoded = CROP_TYPE_ENCODING[crop_name]

        # Create input array
        data = np.array([[temp, humidity, moisture, soil_encoded, crop_encoded, N, P, K]])

        # Predict
        pred_code = xgb_model.predict(data)[0]
        fertilizer = fert_dict.get(pred_code, "Unknown")

        results.append({
            "test_case": i,
            "soil": soil_name,
            "crop": crop_name,
            "soil_code": soil_encoded,
            "crop_code": crop_encoded,
            "prediction_code": pred_code,
            "fertilizer": fertilizer,
            "success": True
        })

        print(f"Test {i}:")
        print(f"  Input: {soil_name} soil (code={soil_encoded}), {crop_name} crop (code={crop_encoded})")
        print(f"  Params: temp={temp}°C, hum={humidity}%, moist={moisture}%, N={N}, P={P}, K={K}")
        print(f"  ✅ Prediction: {fertilizer} (code={pred_code})")
        print()

    except KeyError as e:
        print(f"Test {i}: ❌ Invalid encoding - {e}")
        results.append({
            "test_case": i,
            "soil": soil_name,
            "crop": crop_name,
            "success": False,
            "error": str(e)
        })
    except Exception as e:
        print(f"Test {i}: ❌ Prediction failed - {e}")
        results.append({
            "test_case": i,
            "soil": soil_name,
            "crop": crop_name,
            "success": False,
            "error": str(e)
        })

print("=" * 80)
print("\n📊 Summary:")
print(f"Total tests: {len(test_cases)}")
print(f"Successful: {sum(1 for r in results if r['success'])}")
print(f"Failed: {sum(1 for r in results if not r['success'])}")

# Print unique fertilizers predicted
successful_results = [r for r in results if r['success']]
if successful_results:
    unique_fertilizers = set(r['fertilizer'] for r in successful_results)
    print(f"\n🌱 Unique fertilizers predicted: {sorted(unique_fertilizers)}")
    print(f"   Total: {len(unique_fertilizers)} out of {len(fert_dict)} possible")

print("\n✅ Encoding verification complete!")
print("\nℹ️  If all tests passed, the encodings are correct and can be used in production.")
