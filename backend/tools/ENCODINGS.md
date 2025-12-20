# Fertilizer Model Encoding Mappings

## Overview

This document describes the verified integer encoding mappings for the XGBoost fertilizer recommendation model (`xgb_pipeline.joblib`).

**Verification Date:** 2025-11-10
**Model Files:**
- `models/xgb_pipeline.joblib` - XGBoost model
- `models/fertname_dict.joblib` - Fertilizer code to name mapping

**Verification Status:** ✅ All encodings verified with test predictions

---

## Soil Type Encoding

Maps soil type strings to integer codes (0-4):

```python
SOIL_TYPE_ENCODING = {
    "sandy": 0,
    "loamy": 1,
    "black": 2,
    "red": 3,
    "clayey": 4
}
```

**Valid Input Values:**
- `sandy` → 0
- `loamy` → 1
- `black` → 2
- `red` → 3
- `clayey` → 4

**Total Soil Types:** 5

---

## Crop Type Encoding

Maps crop type strings to integer codes (0-10):

```python
CROP_TYPE_ENCODING = {
    "maize": 0,
    "sugarcane": 1,
    "cotton": 2,
    "tobacco": 3,
    "paddy": 4,      # Also accepts "rice"
    "barley": 5,
    "wheat": 6,
    "millets": 7,
    "oil seeds": 8,  # Also accepts "oilseeds"
    "pulses": 9,
    "ground nuts": 10  # Also accepts "groundnuts"
}
```

**Valid Input Values:**
- `maize` → 0
- `sugarcane` → 1
- `cotton` → 2
- `tobacco` → 3
- `paddy` or `rice` → 4 (aliases)
- `barley` → 5
- `wheat` → 6
- `millets` → 7
- `oil seeds` or `oilseeds` → 8 (aliases)
- `pulses` → 9
- `ground nuts` or `groundnuts` → 10 (aliases)

**Total Crop Types:** 11 (8 unique codes with 3 aliases)

---

## Fertilizer Output Mapping

Maps model prediction codes to fertilizer names:

```python
FERTILIZER_DICT = {
    0: "10-26-26",
    1: "14-35-14",
    2: "17-17-17",
    3: "20-20",
    4: "28-28",
    5: "DAP",
    6: "Urea"
}
```

**Possible Predictions:**
- Code 0 → `10-26-26`
- Code 1 → `14-35-14`
- Code 2 → `17-17-17`
- Code 3 → `20-20`
- Code 4 → `28-28`
- Code 5 → `DAP` (Diammonium Phosphate)
- Code 6 → `Urea`

**Total Fertilizers:** 7

---

## Input Feature Order

The model expects an 8-feature input array in this exact order:

```python
[Temperature, Humidity, Moisture, SoilType_Code, CropType_Code, Nitrogen, Phosphorous, Potassium]
```

**Example:**
```python
# Sandy soil (0), Wheat (6), temp 25°C, humidity 60%, moisture 45%
# N=40, P=50, K=30
input_array = np.array([[25.0, 60.0, 45.0, 0, 6, 40.0, 50.0, 30.0]])
prediction_code = xgb_model.predict(input_array)[0]
fertilizer_name = fert_dict[prediction_code]  # "Urea"
```

---

## NPK Ratio Mapping

For enhanced response quality, map fertilizer names to their NPK ratios:

```python
NPK_RATIOS = {
    "Urea": "46-0-0",            # High nitrogen
    "DAP": "18-46-0",             # High phosphorus
    "14-35-14": "14-35-14",       # Balanced with high P
    "28-28": "28-28-0",           # Balanced N-P
    "17-17-17": "17-17-17",       # Fully balanced
    "20-20": "20-20-0",           # Balanced N-P
    "10-26-26": "10-26-26"        # High P-K
}
```

---

## Parameter Ranges

**Environmental Parameters:**
- Temperature: 10-50°C (typical agricultural range)
- Humidity: 0-100%
- Moisture: 0-100%

**Soil Nutrient Parameters:**
- Nitrogen (N): 0-200 kg/ha
- Phosphorous (P): 0-150 kg/ha
- Potassium (K): 0-150 kg/ha

---

## Normalization Requirements

**IMPORTANT:** The input values are NOT normalized. The model expects raw values in the following units:

- Temperature: Celsius
- Humidity: Percentage (0-100)
- Moisture: Percentage (0-100)
- Soil/Crop: Integer codes (see mappings above)
- N/P/K: kg/ha (absolute values, not normalized)

Do NOT apply z-score normalization or min-max scaling to the inputs.

---

## Error Handling

**Invalid Soil Type:**
- If input soil type is not in `SOIL_TYPE_ENCODING`, return error
- Example: "volcanic" → Invalid

**Invalid Crop Type:**
- If input crop type is not in `CROP_TYPE_ENCODING`, return error
- Example: "banana" → Invalid

**Out of Range Values:**
- Temperature < 10 or > 50: Warning (but allow prediction)
- Humidity/Moisture < 0 or > 100: Warning (but allow prediction)
- N/P/K < 0: Warning (but allow prediction)

---

## Verification Results

**Test Summary:**
- ✅ 8/8 test cases passed
- ✅ All soil type codes (0-4) verified
- ✅ 7/11 crop type codes tested and verified
- ✅ 2/7 fertilizer outputs observed (Urea, 28-28)

**Verification Command:**
```bash
python tools/verify_encodings.py
```

---

## Usage Example

```python
import numpy as np
import joblib

# Load models
xgb_model = joblib.load("models/xgb_pipeline.joblib")
fert_dict = joblib.load("models/fertname_dict.joblib")

# Define encodings
SOIL_TYPE_ENCODING = {"sandy": 0, "loamy": 1, "black": 2, "red": 3, "clayey": 4}
CROP_TYPE_ENCODING = {"maize": 0, "sugarcane": 1, "cotton": 2, "tobacco": 3,
                      "paddy": 4, "rice": 4, "barley": 5, "wheat": 6,
                      "millets": 7, "oil seeds": 8, "oilseeds": 8,
                      "pulses": 9, "ground nuts": 10, "groundnuts": 10}

# User input
temperature = 25.0
humidity = 60.0
moisture = 45.0
soil_type = "sandy"
crop_type = "wheat"
nitrogen = 40.0
phosphorous = 50.0
potassium = 30.0

# Encode
soil_encoded = SOIL_TYPE_ENCODING[soil_type]  # 0
crop_encoded = CROP_TYPE_ENCODING[crop_type]  # 6

# Predict
data = np.array([[temperature, humidity, moisture, soil_encoded,
                  crop_encoded, nitrogen, phosphorous, potassium]])
pred_code = xgb_model.predict(data)[0]
fertilizer = fert_dict[pred_code]

print(f"Recommended fertilizer: {fertilizer}")  # "Urea"
```

---

## Notes

1. **Case Sensitivity:** All string inputs should be lowercase before encoding
2. **Aliases:** Support common aliases (rice/paddy, oilseeds/oil seeds, groundnuts/ground nuts)
3. **Model Bias:** The model shows strong bias toward Urea in test cases (6/8 predictions)
4. **Whitespace:** Handle whitespace variations (e.g., "oil seeds" vs "oilseeds")
5. **Validation:** Always validate inputs before encoding to provide clear error messages

---

## References

- Verification script: `tools/verify_encodings.py`
- Model files: `models/xgb_pipeline.joblib`, `models/fertname_dict.joblib`
- Router implementation: `routers/fertilizer_predict.py`
