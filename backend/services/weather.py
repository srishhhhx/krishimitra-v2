import os
import requests
from dotenv import load_dotenv

load_dotenv()

API_KEY = os.getenv("OPENWEATHER_API_KEY")
BASE_URL = "https://api.openweathermap.org/data/2.5/weather"

# Crop-specific rules keyed by canonical crop names (lowercase)
# Keep the set focused initially; extend as needed
CROP_SPECIFIC_RULES = {

    # 1️⃣ Cereal/Grain Crops
    "rice": {
        "irrigation": [
            {"condition": lambda w, f: w["temperature"] > 35 and w["humidity"] < 40,
             "message": "🌾 Rice under high temp & low humidity: Irrigate frequently to maintain waterlogged soil."},
            {"condition": lambda w, f: w["rain_1h"] > 5,
             "message": "🌧 Rice currently raining: Skip irrigation to prevent waterlogging."}
        ],
        "pest_alert": [
            {"condition": lambda w, f: w["humidity"] > 80 and w["temperature"] > 25,
             "message": "🌾 Rice blast risk: Monitor leaves, apply preventive fungicide."}
        ],
        "harvest_tips": [
            {"condition": lambda w, f: w["rain_1h"] > 5 or w.get("rain_3h", 0) > 10,
             "message": "⛔ Avoid harvesting rice: Wet conditions may damage grains."}
        ],
        "fertilizer_tips": [
            {"condition": lambda w, f: w["temperature"] > 35,
             "message": "🔥 Hot & dry: Avoid fertilizer application on rice, focus on irrigation first."}
        ],
        "crop_health": [
            {"condition": lambda w, f: w["temperature"] > 38 and w["humidity"] < 35,
             "message": "🌵 Rice under drought stress: Provide shade, increase irrigation."}
        ]
    },
    "wheat": {
        "irrigation": [
            {"condition": lambda w, f: f.get("soil_moisture", 50) < 60,
             "message": "🌾 Wheat soil moisture moderate: Consider irrigation to maintain optimal growth."}
        ],
        "pest_alert": [
            {"condition": lambda w, f: w["humidity"] > 70,
             "message": "🌾 High humidity detected: Monitor wheat for rust or aphid risk and inspect regularly."}
        ],
        "harvest_tips": [
            {"condition": lambda w, f: w["temperature"] > 20 and w["humidity"] < 80,
             "message": "🌾 Good conditions for wheat: Harvest timing is favorable with current weather."}
        ],
        "fertilizer_tips": [
            {"condition": lambda w, f: w["temperature"] > 15 and w["temperature"] < 30,
             "message": "🌾 Optimal temperature for wheat fertilizer application: Apply balanced NPK."}
        ],
        "crop_health": [
            {"condition": lambda w, f: w["humidity"] > 75,
             "message": "🌾 High humidity may stress wheat: Monitor for fungal diseases and ensure good air circulation."}
        ]
    },
    "maize": {
        "irrigation": [
            {"condition": lambda w, f: f.get("soil_moisture", 50) < 60,
             "message": "🌽 Maize soil moisture moderate: Consider irrigation for optimal growth."}
        ],
        "pest_alert": [
            {"condition": lambda w, f: w["temperature"] > 20 and w["humidity"] > 70,
             "message": "🌽 Maize may face stem borer/fungal risk: Monitor daily and inspect leaves."}
        ],
        "harvest_tips": [
            {"condition": lambda w, f: w["temperature"] > 15 and w["humidity"] < 85,
             "message": "🌽 Good conditions for maize harvest: Weather is suitable for field operations."}
        ],
        "fertilizer_tips": [
            {"condition": lambda w, f: w["temperature"] > 18 and w["temperature"] < 35,
             "message": "🌽 Optimal temperature for maize fertilizer: Apply nitrogen-rich fertilizer."}
        ],
        "crop_health": [
            {"condition": lambda w, f: w["humidity"] > 75,
             "message": "🌽 High humidity may stress maize: Monitor for leaf diseases and ensure good drainage."}
        ]
    },
    "barley": {
        "irrigation": [
            {"condition": lambda w, f: f["soil_moisture"] < 25,
             "message": "🌾 Barley soil moisture low: Irrigate moderately."}
        ],
        "pest_alert": [
            {"condition": lambda w, f: w["humidity"] > 80,
             "message": "🌾 Powdery mildew risk on barley: Apply fungicide."}
        ],
        "harvest_tips": [
            {"condition": lambda w, f: w["temperature"] > 28,
             "message": "🌾 Dry conditions ideal for barley harvesting."}
        ],
        "fertilizer_tips": [
            {"condition": lambda w, f: w["temperature"] > 35,
             "message": "🔥 Avoid fertilizer in hot weather, irrigate barley first."}
        ],
        "crop_health": [
            {"condition": lambda w, f: w["temperature"] < 5,
             "message": "❄️ Frost risk for barley: Protect young plants."}
        ]
    },
    "sorghum": {
        "irrigation": [
            {"condition": lambda w, f: f["soil_moisture"] < 20,
             "message": "🌾 Sorghum needs irrigation in dry soil conditions."}
        ],
        "pest_alert": [
            {"condition": lambda w, f: w["temperature"] > 32,
             "message": "🌾 Monitor for shoot fly and aphids in sorghum."}
        ],
        "harvest_tips": [
            {"condition": lambda w, f: w["humidity"] < 50,
             "message": "🌾 Sorghum harvest best during dry weather."}
        ],
        "fertilizer_tips": [
            {"condition": lambda w, f: f["soil_moisture"] < 25,
             "message": "💧 Irrigate before fertilizer application to sorghum."}
        ],
        "crop_health": [
            {"condition": lambda w, f: w["temperature"] > 38 and w["humidity"] < 35,
             "message": "🌵 Sorghum drought stress: Monitor leaves, provide irrigation."}
        ]
    },
    "millet": {
        "irrigation": [
            {"condition": lambda w, f: f["soil_moisture"] < 20,
             "message": "🌾 Millet requires irrigation during dry spells."}
        ],
        "pest_alert": [
            {"condition": lambda w, f: w["humidity"] > 75,
             "message": "🌾 High humidity: Monitor millet for leaf spot/fungal disease."}
        ],
        "harvest_tips": [
            {"condition": lambda w, f: w["temperature"] > 30 and w["humidity"] < 50,
             "message": "🌾 Millet harvest is optimal in dry, warm weather."}
        ],
        "fertilizer_tips": [
            {"condition": lambda w, f: f["soil_moisture"] < 25,
             "message": "💧 Irrigate before fertilizer application to millet."}
        ],
        "crop_health": [
            {"condition": lambda w, f: w["temperature"] > 38 and w["humidity"] < 35,
             "message": "🌵 Millet drought stress: Increase watering, monitor leaf wilting."}
        ]
    },
    "oats": {
        "irrigation": [
            {"condition": lambda w, f: f["soil_moisture"] < 25,
             "message": "🌾 Oats soil moisture low: Irrigate as needed."}
        ],
        "pest_alert": [
            {"condition": lambda w, f: w["humidity"] > 80,
             "message": "🌾 Oats fungal risk high: Inspect for rust and mildew."}
        ],
        "harvest_tips": [
            {"condition": lambda w, f: w["temperature"] > 28,
             "message": "🌾 Oats harvest under warm, dry conditions is best."}
        ],
        "fertilizer_tips": [
            {"condition": lambda w, f: w["temperature"] > 35,
             "message": "🔥 Avoid fertilizer in hot weather; irrigate oats first."}
        ],
        "crop_health": [
            {"condition": lambda w, f: w["temperature"] < 5,
             "message": "❄️ Frost risk for oats: Protect young plants."}
        ]
    },

    # 2️⃣ Pulses/Legumes
    "chickpea": {
        "irrigation": [
            {"condition": lambda w, f: f["soil_moisture"] < 20,
             "message": "🌱 Chickpea requires irrigation in dry soil."}
        ],
        "pest_alert": [
            {"condition": lambda w, f: w["temperature"] > 30,
             "message": "🌱 Watch for pod borer or aphid infestation in chickpea."}
        ],
        "harvest_tips": [
            {"condition": lambda w, f: w["humidity"] < 40,
             "message": "🌱 Harvest chickpea when pods are dry."}
        ],
        "fertilizer_tips": [
            {"condition": lambda w, f: f["soil_moisture"] < 25,
             "message": "💧 Irrigate chickpea before fertilizer application."}
        ],
        "crop_health": [
            {"condition": lambda w, f: w["temperature"] > 35,
             "message": "🔥 Heat stress in chickpea: Provide shade and monitor for wilting."}
        ]
    },
    "lentils": {
        "irrigation": [
            {"condition": lambda w, f: f["soil_moisture"] < 18,
             "message": "🌱 Lentils need light irrigation in dry periods."}
        ],
        "pest_alert": [
            {"condition": lambda w, f: w["humidity"] > 80,
             "message": "🌱 High humidity: Monitor lentils for fungal infections."}
        ],
        "harvest_tips": [
            {"condition": lambda w, f: w["temperature"] > 28,
             "message": "🌱 Lentils should be harvested during dry weather."}
        ],
        "fertilizer_tips": [
            {"condition": lambda w, f: f["soil_moisture"] < 20,
             "message": "💧 Irrigate before fertilizer application to lentils."}
        ],
        "crop_health": [
            {"condition": lambda w, f: w["temperature"] > 35,
             "message": "🔥 Heat stress in lentils: Provide shade and maintain soil moisture."}
        ]
    },
    "black gram": {
        "irrigation": [
            {"condition": lambda w, f: f["soil_moisture"] < 20 and w["temperature"] > 32,
             "message": "🌱 Black Gram: Urgent irrigation required in hot, dry conditions."},
        ],
        "pest_alert": [
            {"condition": lambda w, f: w["temperature"] > 28 and w["humidity"] > 70,
             "message": "🌱 Black Gram: Monitor for Yellow Mosaic Virus (YMV) vector (whitefly)."},
        ],
        "harvest_tips": [
            {"condition": lambda w, f: w["humidity"] > 60 and w["rain_1h"] > 0,
             "message": "⛔ Avoid harvesting Black Gram; wait for dry conditions to prevent seed damage."},
        ],
        "fertilizer_tips": [
            {"condition": lambda w, f: f.get("soil_ph", 7.0) < 6.0, # Added .get() and default for safety
             "message": "🧪 Black Gram: Consider lime application; check soil nutrient status before N/P/K."}
        ],
        "crop_health": [
            {"condition": lambda w, f: w["temperature"] < 15,
             "message": "🥶 Black Gram: Low temperatures can stunt growth; ensure sufficient mulching."}
        ]
    },
    "soybean": {
        "irrigation": [
            {"condition": lambda w, f: f.get("soil_moisture", 50) < 60,
             "message": "🌱 Soybean: Maintain adequate soil moisture for optimal pod filling."}
        ],
        "pest_alert": [
            {"condition": lambda w, f: w["humidity"] > 75 and w["temperature"] > 20,
             "message": "🌱 Soybean: Monitor for rust and pod borer; high humidity increases risk."}
        ],
        "harvest_tips": [
            {"condition": lambda w, f: w["temperature"] > 25 and w["humidity"] < 70,
             "message": "🌱 Soybean: Good conditions for harvest; pods should be dry and rattling."}
        ],
        "fertilizer_tips": [
            {"condition": lambda w, f: w["temperature"] > 18 and w["temperature"] < 32,
             "message": "🌱 Soybean: Apply phosphorus and potassium; nitrogen fixation reduces N needs."}
        ],
        "crop_health": [
            {"condition": lambda w, f: w["humidity"] > 80,
             "message": "🌱 Soybean: High humidity may cause fungal diseases; ensure good air circulation."}
        ]
    },
    # Note: Rules for Green Gram, Pigeon Pea, Peas should be added here to complete the Pulses/Legumes category.

    # 3️⃣ Oilseeds
    "groundnut": {
        "irrigation": [
            {"condition": lambda w, f: f["soil_moisture"] < 25,
             "message": "🥜 Groundnut: Critical irrigation needed, especially during pegging/pod filling."},
        ],
        "pest_alert": [
            {"condition": lambda w, f: w["humidity"] > 75 and w["temperature"] > 25,
             "message": "🥜 Groundnut: High risk of Leaf Spot/Rust; apply preventive fungicide."},
        ],
        "harvest_tips": [
            {"condition": lambda w, f: w["rain_1h"] > 0,
             "message": "⛔ Groundnut: Avoid harvesting in wet conditions; pods may rot or quality will decrease."},
        ],
        "fertilizer_tips": [
            {"condition": lambda w, f: f.get("calcium_deficiency"),
             "message": "⚠️ Groundnut: Apply gypsum (Calcium) during flowering/pegging for better pod filling."}
        ],
        "crop_health": [
            {"condition": lambda w, f: w["temperature"] > 38,
             "message": "🔥 Groundnut: Severe heat stress; irrigate heavily and look for wilting/scorch."}
        ]
    },
    "mustard": {
        "irrigation": [
            {"condition": lambda w, f: f.get("soil_moisture", 50) < 50,
             "message": "🌻 Mustard: Moderate irrigation needed, especially during flowering and pod filling."}
        ],
        "pest_alert": [
            {"condition": lambda w, f: w["humidity"] > 70 and w["temperature"] > 20,
             "message": "🌻 Mustard: Monitor for aphids and white rust; apply appropriate pesticides."}
        ],
        "harvest_tips": [
            {"condition": lambda w, f: w["temperature"] > 25 and w["humidity"] < 60,
             "message": "🌻 Mustard: Good conditions for harvest; pods should be mature and dry."}
        ],
        "fertilizer_tips": [
            {"condition": lambda w, f: w["temperature"] > 15 and w["temperature"] < 30,
             "message": "🌻 Mustard: Apply nitrogen and sulfur fertilizer for better oil content."}
        ],
        "crop_health": [
            {"condition": lambda w, f: w["humidity"] > 75,
             "message": "🌻 Mustard: High humidity may cause fungal diseases; ensure good field drainage."}
        ]
    },
    # Note: Rules for Sunflower, Sesame, Coconut should be added here to complete the Oilseeds category.

    # 4️⃣ Cash/Plantation Crops
    "sugarcane": {
        "irrigation": [
            {"condition": lambda w, f: f["soil_moisture"] < 35,
             "message": "🌿 Sugarcane: Heavy irrigation needed to maintain growth, especially in summer."},
        ],
        "pest_alert": [
            {"condition": lambda w, f: w["temperature"] > 30 and w["humidity"] > 60,
             "message": "🌿 Sugarcane: Monitor for shoot borer/red rot risk under warm, humid conditions."},
        ],
        "harvest_tips": [
            {"condition": lambda w, f: w["rain_1h"] > 5,
             "message": "⛔ Sugarcane: Postpone harvest; wet conditions lower sugar recovery and soil damage."},
        ],
        "fertilizer_tips": [
            {"condition": lambda w, f: f.get("soil_nitrogen") == "low",
             "message": "🧪 Sugarcane: Apply high nitrogen fertilizer in the early growth stage."},
        ],
        "crop_health": [
            {"condition": lambda w, f: w["temperature"] < 10,
             "message": "🥶 Sugarcane: Cold weather stress; avoid harvesting as sugar content may be low."}
        ]
    },
    # Note: Rules for Cotton, Tea, Coffee, Rubber, Tobacco should be added here to complete the Cash/Plantation category.

    # 5️⃣ Vegetables
    "tomato": {
        "irrigation": [
            {"condition": lambda w, f: f.get("soil_moisture", 50) < 60,
             "message": "🍅 Tomato: Consistent watering is critical to prevent blossom end rot."},
        ],
        "pest_alert": [
            {"condition": lambda w, f: w["humidity"] > 75 and w["temperature"] > 15,
             "message": "🍅 Tomato: High risk of late blight; apply protectant fungicide immediately."},
        ],
        "harvest_tips": [
            {"condition": lambda w, f: w["temperature"] > 20 and w["humidity"] < 85,
             "message": "🍅 Tomato: Good conditions for harvest; pick ripe fruits early in the day."},
        ],
        "fertilizer_tips": [
            {"condition": lambda w, f: w["temperature"] > 18 and w["temperature"] < 32,
             "message": "🍅 Tomato: Apply potassium-rich fertilizer during fruiting stage for better quality."},
        ],
        "crop_health": [
            {"condition": lambda w, f: w["humidity"] > 75,
             "message": "🍅 Tomato: High humidity may cause fungal issues; ensure good air circulation."}
        ]
    },
    # Note: Rules for Onion, Potato, Carrot, Cabbage/Cauliflower/Broccoli, Brinjal, Capsicum, Cucumber, Spinach should be added here to complete the Vegetables category.

    # 6️⃣ Fruits
    "mango": {
        "irrigation": [
            {"condition": lambda w, f: f["soil_moisture"] < 25 and f.get("growth_stage") == "flowering",
             "message": "🥭 Mango: Avoid heavy irrigation during flowering to promote fruit set."},
        ],
        "pest_alert": [
            {"condition": lambda w, f: w["humidity"] > 75 and f.get("growth_stage") == "flowering",
             "message": "🥭 Mango: High risk of powdery mildew on flowers; apply systemic fungicide."},
        ],
        "harvest_tips": [
            {"condition": lambda w, f: w["temperature"] > 30,
             "message": "🥭 Mango: Ideal harvest time when temperatures are high and dry."},
        ],
        "fertilizer_tips": [
            {"condition": lambda w, f: f.get("growth_stage") == "pre-flowering",
             "message": "🧪 Mango: Apply nitrogen and phosphorus to support the upcoming bloom."},
        ],
        "crop_health": [
            {"condition": lambda w, f: w["temperature"] < 5,
             "message": "🥶 Mango: Frost/cold damage risk to young flushes; consider light irrigation or smoking."}
        ]
    },
    "banana": {
        "irrigation": [
            {"condition": lambda w, f: w["rain_1h"] == 0 and w["temperature"] > 30,
             "message": "🍌 Banana: Requires frequent, deep irrigation during hot and dry spells."},
        ],
        "pest_alert": [
            {"condition": lambda w, f: w["humidity"] > 80,
             "message": "🍌 Banana: High risk of Sigatoka Leaf Spot; apply protectant fungicide."},
        ],
        "harvest_tips": [
            {"condition": lambda w, f: w["rain_1h"] > 5,
             "message": "⛔ Banana: Harvesting during rain can affect quality and handling; postpone."},
        ],
        "fertilizer_tips": [
            {"condition": lambda w, f: f.get("soil_potassium") == "low",
             "message": "🧪 Banana: Critical need for high Potassium fertilizer to support fruit development."},
        ],
        "crop_health": [
            {"condition": lambda w, f: w["temperature"] < 10,
             "message": "🥶 Banana: Cold damage risk; provide windbreaks or plant in sheltered areas."}
        ]
    },
    "apple": {
        "irrigation": [
            {"condition": lambda w, f: f["soil_moisture"] < 30,
             "message": "🍎 Apple: Maintain consistent soil moisture; irrigate if soil is dry."},
        ],
        "pest_alert": [
            {"condition": lambda w, f: w["humidity"] > 70 and w["temperature"] > 25,
             "message": "🍎 Apple: Monitor for Codling Moth and Apple Scab; apply timely sprays."},
        ],
        "harvest_tips": [
            {"condition": lambda w, f: w["rain_1h"] > 0,
             "message": "⛔ Apple: Avoid harvesting immediately after heavy rain; wait for fruit surface to dry."},
        ],
        "fertilizer_tips": [
            {"condition": lambda w, f: f.get("soil_calcium") == "low",
             "message": "🧪 Apple: Foliar spray of Calcium needed to prevent Bitter Pit."},
        ],
        "crop_health": [
            {"condition": lambda w, f: w["temperature"] < 0,
             "message": "❄️ Apple: Frost warning; use sprinklers or heaters for blossom protection."}
        ]
    },
    "orange": {
        "irrigation": [
            {"condition": lambda w, f: f["soil_moisture"] < 25,
             "message": "🍊 Orange: Irrigate to prevent fruit splitting, especially during dry spells."},
        ],
        "pest_alert": [
            {"condition": lambda w, f: w["temperature"] > 30 and w["humidity"] < 50,
             "message": "🍊 Orange: Monitor for Citrus Mites/Thrips; spray with suitable miticide."},
        ],
        "harvest_tips": [
            {"condition": lambda w, f: w["humidity"] > 80,
             "message": "⛔ Orange: High humidity can promote mold; harvest on dry days."},
        ],
        "fertilizer_tips": [
            {"condition": lambda w, f: f.get("soil_zinc") == "low",
             "message": "🧪 Orange: Apply Zinc and Manganese foliar sprays for healthy leaf development."},
        ],
        "crop_health": [
            {"condition": lambda w, f: w["temperature"] < 5,
             "message": "🥶 Orange: Frost risk; cover young trees or use micro-sprinklers."}
        ]
    },
    "grapes": {
        "irrigation": [
            {"condition": lambda w, f: f["soil_moisture"] < 30 and f.get("growth_stage") == "berry swelling",
             "message": "🍇 Grapes: Moderate irrigation needed during berry swelling; avoid overwatering."},
        ],
        "pest_alert": [
            {"condition": lambda w, f: w["humidity"] > 75 and w["rain_1h"] > 0,
             "message": "🍇 Grapes: High risk of Downy Mildew; apply fungicide before next rain."},
        ],
        "harvest_tips": [
            {"condition": lambda w, f: w["rain_1h"] > 1,
             "message": "⛔ Grapes: Do not harvest during rain or when vines are wet; high rot risk."},
        ],
        "fertilizer_tips": [
            {"condition": lambda w, f: f.get("soil_potassium") == "low",
             "message": "🧪 Grapes: Potassium application essential for sugar development in berries."},
        ],
        "crop_health": [
            {"condition": lambda w, f: w["temperature"] > 35,
             "message": "🔥 Grapes: Heat stress; may lead to sunburn or uneven ripening. Use shade nets."}
        ]
    },
    "pomegranate": {
        "irrigation": [
            {"condition": lambda w, f: f["soil_moisture"] < 25,
             "message": "🔴 Pomegranate: Consistent irrigation is crucial to prevent fruit cracking."},
        ],
        "pest_alert": [
            {"condition": lambda w, f: w["temperature"] > 30,
             "message": "🔴 Pomegranate: Monitor for fruit borer/anar butterfly; apply preventive measures."},
        ],
        "harvest_tips": [
            {"condition": lambda w, f: w["rain_1h"] > 0,
             "message": "⛔ Pomegranate: Avoid harvesting in wet weather; it increases post-harvest decay."},
        ],
        "fertilizer_tips": [
            {"condition": lambda w, f: f.get("soil_boron") == "low",
             "message": "🧪 Pomegranate: Boron deficiency can cause cracking; apply foliar spray."},
        ],
        "crop_health": [
            {"condition": lambda w, f: w["temperature"] > 40,
             "message": "🔥 Pomegranate: Extreme heat; provide heavy mulching and light irrigation."}
        ]
    },
    "papaya": {
        "irrigation": [
            {"condition": lambda w, f: f["soil_moisture"] < 30,
             "message": "🥭 Papaya: Water regularly, but avoid waterlogging to prevent collar rot."},
        ],
        "pest_alert": [
            {"condition": lambda w, f: w["temperature"] > 25 and w["humidity"] > 70,
             "message": "🥭 Papaya: High risk of viral disease (PRSV); monitor and remove infected plants."},
        ],
        "harvest_tips": [
            {"condition": lambda w, f: w["rain_1h"] > 5,
             "message": "⛔ Papaya: Postpone harvest; wet fruit is highly susceptible to fungal spoilage."},
        ],
        "fertilizer_tips": [
            {"condition": lambda w, f: f.get("soil_nitrogen") == "low",
             "message": "🧪 Papaya: Apply balanced NPK fertilizer frequently, as it's a heavy feeder."},
        ],
        "crop_health": [
            {"condition": lambda w, f: w["temperature"] < 10,
             "message": "🥶 Papaya: Cold can stop growth and damage leaves; protect from frost."}
        ]
    },
    "guava": {
        "irrigation": [
            {"condition": lambda w, f: f["soil_moisture"] < 25,
             "message": "🍈 Guava: Needs consistent irrigation, especially during fruiting season."},
        ],
        "pest_alert": [
            {"condition": lambda w, f: w["temperature"] > 30,
             "message": "🍈 Guava: Watch for fruit fly infestation; use traps or baiting."},
        ],
        "harvest_tips": [
            {"condition": lambda w, f: w["humidity"] > 80,
             "message": "⛔ Guava: High humidity can cause quick decay; harvest in dry periods."},
        ],
        "fertilizer_tips": [
            {"condition": lambda w, f: f.get("soil_nitrogen") == "low",
             "message": "🧪 Guava: Apply high nitrogen fertilizer after pruning for new growth."},
        ],
        "crop_health": [
            {"condition": lambda w, f: w["temperature"] < 5,
             "message": "🥶 Guava: Young plants are cold-sensitive; provide protection."}
        ]
    },
    "watermelon": {
        "irrigation": [
            {"condition": lambda w, f: f["soil_moisture"] < 30,
             "message": "🍉 Watermelon: Critical watering needed during fruit development; avoid overhead watering."},
        ],
        "pest_alert": [
            {"condition": lambda w, f: w["humidity"] > 80,
             "message": "🍉 Watermelon: High risk of Downy/Powdery Mildew; apply suitable fungicide."},
        ],
        "harvest_tips": [
            {"condition": lambda w, f: w["rain_1h"] > 0,
             "message": "⛔ Watermelon: Avoid harvesting or transport in wet conditions."},
        ],
        "fertilizer_tips": [
            {"condition": lambda w, f: f.get("soil_potassium") == "low",
             "message": "🧪 Watermelon: Apply potassium fertilizer for sweetness and rind strength."},
        ],
        "crop_health": [
            {"condition": lambda w, f: w["temperature"] > 35,
             "message": "🔥 Watermelon: High temperatures are fine, but ensure soil moisture to prevent sun scald."}
        ]
    },

    # 7️⃣ Spices/Herbs
    "turmeric": {
        "irrigation": [
            {"condition": lambda w, f: w["rain_1h"] == 0 and f["soil_moisture"] < 35,
             "message": "🌶️ Turmeric: Needs constant soil moisture; irrigate every 10 days in dry weather."},
        ],
        "pest_alert": [
            {"condition": lambda w, f: w["humidity"] > 85,
             "message": "🌶️ Turmeric: Monitor for leaf spot and rhizome rot; ensure good drainage."},
        ],
        "harvest_tips": [
            {"condition": lambda w, f: w["rain_1h"] > 0,
             "message": "⛔ Turmeric: Avoid harvesting; rhizomes are easier to cure when dug in dry soil."},
        ],
        "fertilizer_tips": [
            {"condition": lambda w, f: f.get("soil_organic_matter") == "low",
             "message": "🧪 Turmeric: Incorporate large quantities of farmyard manure (FYM)."},
        ],
        "crop_health": [
            {"condition": lambda w, f: w["temperature"] < 15,
             "message": "🥶 Turmeric: Low temp will retard growth; provide mulch for soil warmth."}
        ]
    },
    "ginger": {
        "irrigation": [
            {"condition": lambda w, f: w["rain_1h"] == 0 and f["soil_moisture"] < 35,
             "message": "🌶️ Ginger: Needs continuous moisture; irrigate every 7-10 days in dry spells."},
        ],
        "pest_alert": [
            {"condition": lambda w, f: w["humidity"] > 85,
             "message": "🌶️ Ginger: High risk of soft rot; ensure soil is well-drained and avoid waterlogging."},
        ],
        "harvest_tips": [
            {"condition": lambda w, f: w["rain_1h"] > 0,
             "message": "⛔ Ginger: Avoid harvesting in wet conditions; this can cause damage and rot."},
        ],
        "fertilizer_tips": [
            {"condition": lambda w, f: f.get("soil_organic_matter") == "low",
             "message": "🧪 Ginger: Requires large amounts of organic fertilizer or compost."},
        ],
        "crop_health": [
            {"condition": lambda w, f: w["temperature"] > 35,
             "message": "🔥 Ginger: High temp and sun can cause scorching; provide partial shade or mulch."}
        ]
    },
    "garlic": {
        "irrigation": [
            {"condition": lambda w, f: f["soil_moisture"] < 25,
             "message": "🧄 Garlic: Consistent watering is needed; reduce irrigation drastically near harvest."},
        ],
        "pest_alert": [
            {"condition": lambda w, f: w["humidity"] > 70 and w["temperature"] < 20,
             "message": "🧄 Garlic: Watch for Rust and Thrips; spray with appropriate chemicals."},
        ],
        "harvest_tips": [
            {"condition": lambda w, f: w["rain_1h"] > 0,
             "message": "⛔ Garlic: Avoid harvesting; wet soil makes bulbs difficult to cure and store."},
        ],
        "fertilizer_tips": [
            {"condition": lambda w, f: f.get("soil_nitrogen") == "low",
             "message": "🧪 Garlic: Apply nitrogen early in the season, before bulbing begins."},
        ],
        "crop_health": [
            {"condition": lambda w, f: w["temperature"] < 5,
             "message": "🥶 Garlic: Cold temperature promotes good bulbing; protect from extreme frost."}
        ]
    },
    "chili": {
        "irrigation": [
            {"condition": lambda w, f: f["soil_moisture"] < 30,
             "message": "🌶️ Chili: Needs regular watering; stress can cause flower drop and fruit abortion."},
        ],
        "pest_alert": [
            {"condition": lambda w, f: w["temperature"] > 30 and w["humidity"] < 50,
             "message": "🌶️ Chili: Monitor for Thrips and Mites; spray undersides of leaves."},
        ],
        "harvest_tips": [
            {"condition": lambda w, f: w["rain_1h"] > 5,
             "message": "⛔ Chili: Avoid drying harvested chilies outside during rain; move to indoor shelter."},
        ],
        "fertilizer_tips": [
            {"condition": lambda w, f: f.get("soil_phosphorus") == "low",
             "message": "🧪 Chili: Apply phosphorus and potassium for better flowering and fruit set."},
        ],
        "crop_health": [
            {"condition": lambda w, f: w["temperature"] > 40,
             "message": "🔥 Chili: High heat can cause flower drop; increase light irrigation."}
        ]
    },
    "coriander": {
        "irrigation": [
            {"condition": lambda w, f: f["soil_moisture"] < 25,
             "message": "🌿 Coriander: Keep soil consistently moist; light, frequent irrigation is best."},
        ],
        "pest_alert": [
            {"condition": lambda w, f: w["temperature"] > 25,
             "message": "🌿 Coriander: Watch for aphids and powdery mildew; cool, moist conditions help."},
        ],
        "harvest_tips": [
            {"condition": lambda w, f: w["temperature"] > 30,
             "message": "⛔ Coriander: High temperature accelerates bolting; harvest leaves quickly."},
        ],
        "fertilizer_tips": [
            {"condition": lambda w, f: f.get("soil_nitrogen") == "low",
             "message": "🧪 Coriander: Apply nitrogen to promote rapid vegetative growth."},
        ],
        "crop_health": [
            {"condition": lambda w, f: w["temperature"] < 10,
             "message": "🥶 Coriander: Hardy to cold, but protect from heavy frost to prevent leaf damage."}
        ]
    },
    "mint": {
        "irrigation": [
            {"condition": lambda w, f: f["soil_moisture"] < 30,
             "message": "🌿 Mint: Keep soil moist at all times; a heavy drinker, especially in sun."},
        ],
        "pest_alert": [
            {"condition": lambda w, f: w["humidity"] > 80,
             "message": "🌿 Mint: High risk of mint rust; ensure good air circulation."},
        ],
        "harvest_tips": [
            {"condition": lambda w, f: w["temperature"] < 20,
             "message": "🌿 Mint: Harvest when temperatures are cooler for highest essential oil content."},
        ],
        "fertilizer_tips": [
            {"condition": lambda w, f: f.get("soil_nitrogen") == "low",
             "message": "🧪 Mint: Frequent nitrogen feeding helps maintain lush, vigorous growth."},
        ],
        "crop_health": [
            {"condition": lambda w, f: w["temperature"] > 35,
             "message": "🔥 Mint: Heat stress can reduce oil quality; keep soil cool with mulch."}
        ]
    },
    "basil": {
        "irrigation": [
            {"condition": lambda w, f: f["soil_moisture"] < 30,
             "message": "🌿 Basil: Water at the base to prevent fungal issues on the leaves."},
        ],
        "pest_alert": [
            {"condition": lambda w, f: w["humidity"] > 75,
             "message": "🌿 Basil: Monitor for Downy Mildew, especially on the undersides of leaves."},
        ],
        "harvest_tips": [
            {"condition": lambda w, f: f.get("growth_stage") == "flowering",
             "message": "⛔ Basil: Pinch off flowers immediately to keep the plant producing leaves and flavor."},
        ],
        "fertilizer_tips": [
            {"condition": lambda w, f: f.get("soil_nitrogen") == "low",
             "message": "🧪 Basil: Apply a balanced, liquid nitrogen feed every 4-6 weeks."},
        ],
        "crop_health": [
            {"condition": lambda w, f: w["temperature"] < 10,
             "message": "🥶 Basil: Highly cold-sensitive; move indoors or cover to prevent blackening."}
        ]
    }
}

def _normalize_crop_name(name: str) -> str:
    if not name:
        return "generic"
    s = name.strip().lower()
    # remove parenthetical text and take first segment before '/'
    if "(" in s:
        s = s.split("(", 1)[0].strip()
    if "/" in s:
        s = s.split("/", 1)[0].strip()
    
    # Handle common aliases
    if s == "corn":
        s = "maize"
    elif s == "rapeseed":
        s = "mustard"
    
    return s

def get_weather_by_location(city: str, state: str = None, country: str = "IN") -> dict:
    """Fetch current weather for a given location"""
    location_query = f"{city},{country}"
    if state:
        location_query = f"{city},{state},{country}"
    
    params = {
        "q": location_query,
        "appid": API_KEY,
        "units": "metric"  # Celsius
    }
    
    response = requests.get(BASE_URL, params=params)
    if response.status_code != 200:
        raise Exception(f"Weather API failed: {response.text}")
    
    data = response.json()
    
    # Extract precipitation data (rain volume in mm for the last hour)
    rain_data = data.get("rain", {})
    rain_1h = rain_data.get("1h", 0)  # Rain in mm for last 1 hour
    
    weather_info = {
        "temperature": data["main"]["temp"],
        "humidity": data["main"]["humidity"],
        "pressure": data["main"]["pressure"],
        "wind_speed": data["wind"]["speed"],
        "description": data["weather"][0]["description"],
        "rain_1h": rain_1h,  # Recent rainfall in mm
        "rain_3h": rain_data.get("3h", 0),  # Rain in mm for last 3 hours
        "clouds": data["clouds"]["all"]  # Cloud coverage percentage
    }
    
    return weather_info

def get_weather(city: str, state: str = None, country: str = "IN") -> dict:
    """Legacy function for backward compatibility"""
    return get_weather_by_location(city, state, country)

def generate_farm_alerts(weather_info: dict, farm: dict) -> dict:
    """
    Generate comprehensive farm management alerts based on weather data.

    Parameters:
        weather_info: dict with keys temperature, humidity, pressure, wind_speed, description
        farm: dict with keys soil_moisture (0-100%), crop_type, farm_size, recent_rainfall

    Returns:
        dict: {"irrigation": str, "pest_alert": str, "general_tips": str, "harvest_tips": str, "fertilizer_tips": str, "crop_health": str}
    """
    alerts = {
        "irrigation": None, 
        "pest_alert": None, 
        "general_tips": None,
        "harvest_tips": None,
        "fertilizer_tips": None,
        "crop_health": None
    }

    temp = weather_info.get("temperature")
    humidity = weather_info.get("humidity")
    pressure = weather_info.get("pressure", 1013)
    wind_speed = weather_info.get("wind_speed")
    description = weather_info.get("description", "").lower()
    
    # Use actual rainfall data from weather API
    rain_1h = weather_info.get("rain_1h", 0)  # Rain in last 1 hour
    rain_3h = weather_info.get("rain_3h", 0)  # Rain in last 3 hours
    clouds = weather_info.get("clouds", 0)    # Cloud coverage

    soil_moisture = farm.get("soil_moisture", 50)
    crop_type = farm.get("crop_type", "generic")
    # Use actual rainfall data instead of manual input
    recent_rainfall = max(rain_1h, rain_3h)  # Use the higher of 1h or 3h rainfall
    farm_size = farm.get("farm_size", "medium")

    # -------- IRRIGATION ALERTS --------
    if temp > 40 and humidity < 30:
        alerts["irrigation"] = "🔥 Extreme heat & drought: Emergency irrigation needed! Water twice daily."
    elif temp > 35 and humidity < 35:
        alerts["irrigation"] = "⚠️ Hot & dry: Irrigation highly recommended! Water in early morning."
    elif soil_moisture < 20:
        alerts["irrigation"] = "🚨 Critical: Soil moisture extremely low! Irrigate immediately."
    elif soil_moisture < 30:
        alerts["irrigation"] = "💧 Soil moisture low: Start irrigation within 2 hours."
    elif recent_rainfall < 2 and humidity < 40 and temp > 30:
        alerts["irrigation"] = f"🌱 No recent rain ({recent_rainfall}mm) + high temp: Irrigation recommended."
    elif recent_rainfall > 15 and soil_moisture > 80:
        alerts["irrigation"] = f"⛔ Stop irrigation: Heavy rain ({recent_rainfall}mm) has waterlogged soil."
    elif recent_rainfall > 10:
        alerts["irrigation"] = f"🌧 Recent rain ({recent_rainfall}mm): Skip irrigation today, soil is moist."
    elif humidity > 90 and soil_moisture > 70:
        alerts["irrigation"] = "⛔ Skip irrigation: High humidity + adequate soil moisture."
    elif temp < 5:
        alerts["irrigation"] = "❄️ Cold weather: Delay irrigation to prevent root damage."
    elif rain_1h > 5:
        alerts["irrigation"] = f"🌧 Currently raining ({rain_1h}mm/h): No irrigation needed."
    else:
        alerts["irrigation"] = "💧 Irrigation not needed currently."

    # -------- PEST & DISEASE ALERTS --------
    if humidity > 85 and temp > 28:
        alerts["pest_alert"] = f"🐛 High pest activity for {crop_type}: Apply organic pesticides, inspect daily."
    elif humidity > 90 and temp < 22:
        alerts["pest_alert"] = "🦠 High fungal/bacterial risk: Apply fungicide, improve air circulation."
    elif recent_rainfall > 20 and humidity > 85:
        alerts["pest_alert"] = f"🌧 Heavy rain ({recent_rainfall}mm) + humidity: Perfect for fungal outbreak - preventive treatment needed."
    elif rain_1h > 10:
        alerts["pest_alert"] = f"🌧 Heavy current rain ({rain_1h}mm/h): High disease risk, check for waterlogging."
    elif temp > 35 and humidity > 70:
        alerts["pest_alert"] = "🔥 Heat stress + humidity: Monitor for pest damage, provide shade."
    elif wind_speed > 20 and humidity > 80:
        alerts["pest_alert"] = "💨 Wind + humidity: Check for wind-borne diseases, secure plants."
    elif temp < 15 and humidity > 85:
        alerts["pest_alert"] = "❄️ Cold + damp: Watch for root rot, improve drainage."
    elif crop_type.lower() in ["grapevine", "grapes"] and humidity > 70 and temp > 20:
        alerts["pest_alert"] = "🍇 Powdery mildew risk on grapevine: Consider fungicide applications."
    elif crop_type.lower() in ["rice", "paddy"] and humidity > 80 and temp > 25:
        alerts["pest_alert"] = "🌾 Rice blast risk: Monitor for leaf spots, apply preventive fungicide."
    elif recent_rainfall > 5 and clouds > 80:
        alerts["pest_alert"] = f"🌧 Rainy conditions ({recent_rainfall}mm): Monitor for water-borne diseases."
    else:
        alerts["pest_alert"] = "✅ Low pest risk today."

    # -------- HARVEST TIPS --------
    if temp > 30 and humidity < 40 and recent_rainfall < 2:
        alerts["harvest_tips"] = "🌾 Perfect harvest weather: Dry conditions ideal for grain crops."
    elif rain_1h > 5 or recent_rainfall > 10:
        alerts["harvest_tips"] = f"⛔ Avoid harvesting: Recent rain ({recent_rainfall}mm) can damage crops and reduce quality."
    elif "rain" in description or humidity > 80:
        alerts["harvest_tips"] = "⛔ Avoid harvesting: Wet conditions can damage crops and reduce quality."
    elif wind_speed > 15:
        alerts["harvest_tips"] = "💨 Windy conditions: Harvest carefully, secure equipment and crops."
    elif temp < 10:
        alerts["harvest_tips"] = "❄️ Cold weather: Harvest early morning, protect crops from frost."
    elif temp > 35:
        alerts["harvest_tips"] = "🔥 Hot weather: Harvest early morning or evening to avoid heat damage."
    elif pressure < 1000 and clouds > 70:
        alerts["harvest_tips"] = "🌪️ Low pressure + cloudy: Weather may change, consider delaying harvest."
    elif recent_rainfall > 5:
        alerts["harvest_tips"] = f"🌧 Recent rain ({recent_rainfall}mm): Wait for crops to dry before harvesting."
    else:
        alerts["harvest_tips"] = "🌱 Good conditions for harvesting today."

    # -------- FERTILIZER TIPS --------
    if recent_rainfall > 20:
        alerts["fertilizer_tips"] = f"🌧 Recent heavy rain ({recent_rainfall}mm): Wait 2-3 days before applying fertilizer to prevent runoff."
    elif rain_1h > 5:
        alerts["fertilizer_tips"] = f"🌧 Currently raining ({rain_1h}mm/h): Avoid fertilizer application, wait for rain to stop."
    elif temp > 35 and humidity < 40:
        alerts["fertilizer_tips"] = "🔥 Hot & dry: Avoid fertilizer application, focus on irrigation first."
    elif humidity > 85 and temp > 25:
        alerts["fertilizer_tips"] = "💧 High humidity: Good conditions for liquid fertilizer application."
    elif wind_speed > 15:
        alerts["fertilizer_tips"] = "💨 Windy conditions: Avoid fertilizer application to prevent drift."
    elif temp < 15:
        alerts["fertilizer_tips"] = "❄️ Cold weather: Fertilizer absorption will be slow, consider waiting."
    elif soil_moisture < 30:
        alerts["fertilizer_tips"] = "💧 Low soil moisture: Irrigate before applying fertilizer."
    elif recent_rainfall > 5 and recent_rainfall < 15:
        alerts["fertilizer_tips"] = f"🌧 Light rain ({recent_rainfall}mm): Good conditions for fertilizer application."
    else:
        alerts["fertilizer_tips"] = "🌱 Good conditions for fertilizer application today."

    # -------- CROP HEALTH MONITORING --------
    if temp > 40:
        alerts["crop_health"] = "🔥 Extreme heat stress: Provide shade, increase irrigation, monitor wilting."
    elif temp < 5:
        alerts["crop_health"] = "❄️ Frost risk: Cover sensitive crops, consider frost protection measures."
    elif humidity > 95:
        alerts["crop_health"] = "💧 Excessive humidity: Risk of mold, improve ventilation, check for diseases."
    elif pressure < 1000 and "storm" in description:
        alerts["crop_health"] = "⛈ Storm approaching: Secure crops, check drainage, prepare for damage."
    elif wind_speed > 25:
        alerts["crop_health"] = "💨 Strong winds: Check for wind damage, secure tall crops, protect young plants."
    elif temp > 30 and humidity < 30:
        alerts["crop_health"] = "🌵 Drought stress: Monitor leaf wilting, increase watering frequency."
    elif temp > 35 and humidity > 70:
        alerts["crop_health"] = "🔥 Heat + humidity stress: Provide shade, improve air circulation."
    else:
        alerts["crop_health"] = "🌱 Crops are healthy under current conditions."

    # -------- GENERAL FARMING TIPS --------
    if "storm" in description or "heavy rain" in description:
        alerts["general_tips"] = "⛈ Severe weather: Secure equipment, check drainage, protect sensitive crops."
    elif wind_speed > 20:
        alerts["general_tips"] = "💨 Strong winds: Secure irrigation systems, check for wind damage."
    elif temp > 35 and humidity > 70:
        alerts["general_tips"] = "🔥 Hot & humid: Work early morning/evening, stay hydrated, provide crop shade."
    elif temp < 10:
        alerts["general_tips"] = "❄️ Cold weather: Protect sensitive crops, check for frost damage."
    elif pressure < 1000:
        alerts["general_tips"] = "🌪️ Low pressure system: Weather may change rapidly, monitor conditions."
    elif humidity > 90:
        alerts["general_tips"] = "💧 High humidity: Good for seed germination, but watch for diseases."
    elif temp > 30 and humidity < 40:
        alerts["general_tips"] = "🌵 Dry conditions: Focus on irrigation, consider mulching to retain moisture."
    else:
        alerts["general_tips"] = "🌱 Good farming conditions today."

    # -------- CROP-SPECIFIC RULES --------
    try:
        primary = farm.get("primary_crops")
        if not primary:
            # fallback to single crop_type field
            primary = [farm.get("crop_type", "generic")]
        matched_msgs = {k: [] for k in alerts.keys()}
        matched_per_crop: dict[str, dict[str, list[str]]] = {}
        
        for raw_name in primary:
            key = _normalize_crop_name(str(raw_name))
            rules = CROP_SPECIFIC_RULES.get(key)
            
            if not rules:
                continue
                
            for category, rule_list in rules.items():
                for rule in rule_list:
                    cond = rule.get("condition")
                    msg = rule.get("message")
                    if callable(cond) and msg:
                        try:
                            condition_met = cond(weather_info, farm)
                            if condition_met:
                                # prefix with crop name for clarity
                                prefixed = f"[{raw_name}] {msg}"
                                matched_msgs[category].append(prefixed)
                                crop_bucket = matched_per_crop.setdefault(str(raw_name), {})
                                crop_bucket.setdefault(category, []).append(msg)
                        except Exception:
                            # ignore condition evaluation errors
                            pass
        
        # Don't merge crop-specific messages into general alerts since we display them separately
        # Just add the crop_specific_alerts to the response
        if matched_per_crop:
            alerts["crop_specific_alerts"] = matched_per_crop
    except Exception as e:
        # fail-safe: never break alerts generation
        print(f"DEBUG: Exception in crop-specific rules: {e}")
        pass

    return alerts

