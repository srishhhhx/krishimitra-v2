"""
Crop Recommendation Agent (Refactored for Orchestrator V2)

This agent handles crop recommendation queries using the Naive Bayes model
through the crop_recommendation_tool.

**Refactored for Orchestrator V2:**
- Uses `collected_findings["crop_agent"]` pattern
- Optional clarification support for critical parameters
- Maintains all existing functionality (LLM extraction, Hindi support, regional inference)

**Key Features:**
- LLM-based extraction of 7 soil/climate parameters
- Smart defaults for missing values (MVP approach)
- Multi-language support (Hindi/Hinglish)
- Regional inference (location-based climate defaults)
- Parameter validation

**Parameters (all optional with defaults):**
- N (Nitrogen): default 50.0 kg/ha
- P (Phosphorus): default 50.0 kg/ha
- K (Potassium): default 50.0 kg/ha
- temperature: default 25.0°C
- humidity: default 65.0%
- ph: default 6.5
- rainfall: default 100.0mm

**Design Decision (MVP):**
For Phase 1, we apply intelligent defaults for ALL missing parameters.
No clarification requested - prioritizing quick responses.

**Future Optimization (Phase 2):**
- Request clarification if location not provided (for better defaults)
- Integrate with WeatherAgent for real-time temp/humidity/rainfall
- Integrate with SoilAgent for NPK/pH based on user's farm location
"""

import json
import re
from typing import Dict, Any, Optional

from agents.base import ToolAgent, track_latency
from schemas.agents import AgentState
from tools.crop_recommendation_tool import recommend_crop, apply_defaults, DEFAULT_VALUES
from core.logging import get_logger
from core.regional_data import get_climate_for_location

logger = get_logger(__name__)


# ============================================================================
# Parameter Extraction Constants
# ============================================================================

# Reasonable ranges for validation
PARAMETER_RANGES = {
    "N": (0, 200),          # Nitrogen kg/ha
    "P": (0, 200),          # Phosphorus kg/ha
    "K": (0, 300),          # Potassium kg/ha
    "temperature": (-10, 60),  # Celsius
    "humidity": (0, 100),   # Percentage
    "ph": (0, 14),          # pH scale
    "rainfall": (0, 500)    # mm per year
}


class CropAgent(ToolAgent):
    """
    Agent for crop recommendation using Naive Bayes model (Refactored for Orchestrator V2)

    This agent:
    1. Extracts 7 parameters from natural language using LLM
    2. Applies intelligent defaults for missing non-critical parameters
    3. Validates parameter ranges
    4. Executes crop recommendation tool
    5. Updates state with results in collected_findings pattern

    **MVP Approach:**
    - All parameters optional (no clarification)
    - Applies sensible defaults immediately
    - Returns recommendation quickly

    **Orchestrator V2 Integration:**
    - Uses collected_findings["crop_agent"] instead of crop_output
    - Matches FertilizerAgent and GeneralRAGWrapper patterns
    - Compatible with async orchestration
    """

    def __init__(self, generation_service):
        """
        Initialize Crop Recommendation Agent

        Args:
            generation_service: Service for LLM generation (used for parameter extraction)
        """
        super().__init__(
            name="crop_agent",
            description="Provides crop recommendations based on soil nutrients and environmental conditions",
            tool_callable=recommend_crop
        )
        self.generation_service = generation_service

    @track_latency("crop_agent")
    async def run(self, state: AgentState) -> AgentState:
        """
        Execute crop recommendation workflow (with collected_findings pattern)

        Workflow:
        1. Extract 7 parameters from user_query using LLM
        2. Apply defaults for missing parameters
        3. Validate parameter ranges
        4. Execute crop recommendation tool
        5. Update state with results in collected_findings["crop_agent"]

        Args:
            state: Current agent state with user_query

        Returns:
            Updated state with collected_findings["crop_agent"] containing:
                status: "success" | "error"
                data: {
                    recommended_crop: Primary crop recommendation
                    confidence_percentage: Confidence score (0-100)
                    alternatives: List of alternative crops
                    input_parameters: Parameters used
                    defaults_applied: Which defaults were used
                    metadata: Additional info
                }
        """
        try:
            query = state.get("user_query", "")
            if not query:
                logger.warning(f"{self.name}: No query provided")
                if state.get("collected_findings") is None:
                    state["collected_findings"] = {}
                state["collected_findings"][self.name] = {
                    "status": "error",
                    "error": "No query provided"
                }
                return state

            logger.info(f"{self.name}: Processing query: {query[:100]}...")

            # Phase 0.1: Detect multi-crop request (e.g., "5 best crops for Punjab")
            requested_count = self._detect_multi_crop_request(query)
            if requested_count > 1:
                logger.info(f"{self.name}: Multi-crop request detected, will return top {requested_count} crops")
                # Store in user_context for response formatting  
                if "user_context" not in state:
                    state["user_context"] = {}
                state["user_context"]["requested_crop_count"] = requested_count

            # Phase 0: Check if user explicitly stated a crop preference (BUG FIX #8)
            user_stated_crop = self._detect_user_crop_preference(query)
            if user_stated_crop:
                logger.info(f"{self.name}: User explicitly wants to grow: {user_stated_crop}")
                # User stated preference - acknowledge it instead of recommending
                if state.get("collected_findings") is None:
                    state["collected_findings"] = {}
                state["collected_findings"][self.name] = {
                    "status": "success",
                    "data": {
                        "user_stated_crop": user_stated_crop,
                        "is_recommendation": False,
                        "message": f"You mentioned wanting to grow {user_stated_crop}. That's a great choice!",
                        "recommended_crop": user_stated_crop,  # For inter-agent sharing
                        "confidence_percentage": 100.0,  # User preference = 100% confidence
                        "metadata": {
                            "user_preference_detected": True,
                            "source": "explicit_user_statement"
                        }
                    }
                }
                if state.get("executed_agents") is None:
                    state["executed_agents"] = []
                state["executed_agents"].append(self.name)
                return state

            # Phase 0.5: Read supervisor-extracted values from user_context (NEW - LLM consolidation)
            supervisor_extracted = {}
            user_context = state.get("user_context", {})
            
            # Map supervisor extraction keys to crop_agent parameter names
            context_mapping = {
                "n_value": "N",
                "p_value": "P", 
                "k_value": "K",
                "temperature": "temperature",
                "humidity": "humidity",
                "ph": "ph",
                "rainfall": "rainfall"
            }
            
            for context_key, param_key in context_mapping.items():
                if user_context.get(context_key) is not None:
                    supervisor_extracted[param_key] = float(user_context[context_key])
            
            if supervisor_extracted:
                logger.info(f"{self.name}: Supervisor-extracted params: {supervisor_extracted}")

            # Phase 0.6: Infer NPK from soil_type if supervisor extracted it (CRITICAL FIX)
            # This ensures "sandy soil in Pune" uses sandy soil NPK values, not defaults
            soil_type = user_context.get("soil_type")
            if soil_type and "N" not in supervisor_extracted:
                soil_npk_mapping = {
                    "sandy": {"N": 20, "P": 20, "K": 20, "ph": 6.5},
                    "loamy": {"N": 60, "P": 50, "K": 50, "ph": 6.5},
                    "black": {"N": 60, "P": 40, "K": 80, "ph": 7.5},
                    "red": {"N": 40, "P": 30, "K": 30, "ph": 5.5},
                    "clay": {"N": 80, "P": 40, "K": 40, "ph": 6.0},
                    "clayey": {"N": 80, "P": 40, "K": 40, "ph": 6.0},
                    "alluvial": {"N": 60, "P": 45, "K": 45, "ph": 7.0},
                }
                soil_lower = soil_type.lower().strip()
                if soil_lower in soil_npk_mapping:
                    npk_values = soil_npk_mapping[soil_lower]
                    for key, value in npk_values.items():
                        if key not in supervisor_extracted:
                            supervisor_extracted[key] = float(value)
                    logger.info(f"{self.name}: Inferred NPK from soil_type '{soil_type}': {npk_values}")

            # Phase 0.7: Infer NPK from location using regional soil database (NEW - location-based inference)
            # This ensures "What crop for Pune?" uses Pune's actual soil NPK values
            location = user_context.get("location")
            if location and "N" not in supervisor_extracted:
                from core.regional_data import get_soil_for_location
                regional_soil = get_soil_for_location(location)
                if regional_soil:
                    for key in ["N", "P", "K", "ph"]:
                        if key in regional_soil and key not in supervisor_extracted:
                            supervisor_extracted[key] = float(regional_soil[key])
                    # Also capture soil_type for logging
                    if not soil_type and regional_soil.get("soil_type"):
                        user_context["soil_type"] = regional_soil["soil_type"]
                    logger.info(f"{self.name}: Inferred NPK from location '{location}': {regional_soil}")

            # Phase 0.8: Read real-time weather from weather_agent if available (MULTI-AGENT CHAIN)
            # This enables Weather → Crop chain where crop agent uses actual weather data
            weather_findings = state.get("collected_findings", {}).get("weather_agent", {})
            if weather_findings.get("status") == "success":
                weather_data = weather_findings.get("data", {})
                # Map weather fields to crop agent parameters
                weather_mapping = {
                    "temperature": "temperature",
                    "humidity": "humidity",
                    # Note: weather API doesn't provide rainfall, but we could estimate from forecast
                }
                for weather_key, param_key in weather_mapping.items():
                    if weather_data.get(weather_key) is not None:
                        # Only use weather data if not already explicitly provided by user
                        if supervisor_extracted.get(param_key) is None:
                            supervisor_extracted[param_key] = float(weather_data[weather_key])
                            logger.info(f"{self.name}: Using real-time weather {param_key}={weather_data[weather_key]}")
                
                # Store weather location in context for later use
                if weather_data.get("location_name"):
                    user_context["weather_location"] = weather_data["location_name"]

            # Phase 1: Extract parameters from natural language using LLM
            extracted_params = await self._extract_parameters_with_llm(query, state)
            logger.info(f"{self.name}: LLM-extracted parameters: {extracted_params}")

            # Phase 1.25: Merge supervisor-extracted values (supervisor takes precedence)
            for param_key, value in supervisor_extracted.items():
                if value is not None:
                    extracted_params[param_key] = value
                    logger.info(f"{self.name}: Using supervisor-extracted {param_key}={value}")

            # Phase 1.5: Apply regional climate defaults (CRITICAL FIX - BUG: jute always recommended)
            # Check for location in user_context or query and use regional climate
            extracted_params = self._apply_regional_climate(state, extracted_params)

            # Phase 2: Apply generic defaults ONLY for still-missing parameters
            complete_params, defaults_used = self._apply_defaults_with_tracking(extracted_params)

            if defaults_used:
                logger.info(f"{self.name}: Applied defaults for: {defaults_used}")
            else:
                logger.info(f"{self.name}: All parameters provided by user")

            # Phase 3: Validate parameters
            validation_errors = self._validate_parameters(complete_params)
            if validation_errors:
                logger.error(f"{self.name}: Validation errors: {validation_errors}")
                if state.get("collected_findings") is None:
                    state["collected_findings"] = {}
                state["collected_findings"][self.name] = {
                    "status": "error",
                    "error": "; ".join(validation_errors),
                    "extracted_params": extracted_params,
                    "validation_errors": validation_errors
                }
                return state

            # Phase 4: Execute crop recommendation tool
            logger.info(f"{self.name}: Calling crop recommendation tool")

            result = self.tool_callable.invoke({
                "N": complete_params["N"],
                "P": complete_params["P"],
                "K": complete_params["K"],
                "temperature": complete_params["temperature"],
                "humidity": complete_params["humidity"],
                "ph": complete_params["ph"],
                "rainfall": complete_params["rainfall"]
            })

            # Phase 5: Check for errors in tool result
            if "error" in result and result["error"]:
                logger.error(f"{self.name}: Tool error: {result['error']}")
                if state.get("collected_findings") is None:
                    state["collected_findings"] = {}
                state["collected_findings"][self.name] = {
                    "status": "error",
                    "error": result["error"]
                }
                return state

            # Phase 6: Format as collected_findings (orchestrator V2 pattern)
            if state.get("collected_findings") is None:
                state["collected_findings"] = {}

            state["collected_findings"][self.name] = {
                "status": "success",
                "data": {
                    "recommended_crop": result.get("recommended_crop"),
                    "confidence_percentage": result.get("confidence_percentage", 0.0),
                    "alternatives": result.get("alternatives", []),
                    "input_parameters": result.get("input_parameters", {}),
                    "defaults_applied": defaults_used,
                    "requested_crop_count": state.get("user_context", {}).get("requested_crop_count", 1),
                    "metadata": {
                        **result.get("metadata", {}),
                        "defaults_used": bool(defaults_used),
                        "extracted_params": extracted_params,
                        "multi_crop_request": state.get("user_context", {}).get("requested_crop_count", 1) > 1
                    }
                }
            }

            # Phase 7: Track agent execution
            if state.get("executed_agents") is None:
                state["executed_agents"] = []
            state["executed_agents"].append(self.name)

            logger.info(
                f"{self.name}: Recommended crop: {result.get('recommended_crop')} "
                f"(confidence: {result.get('confidence_percentage', 0):.2f}%)"
            )

            return state

        except Exception as e:
            logger.error(f"{self.name} failed: {e}", exc_info=True)
            if state.get("collected_findings") is None:
                state["collected_findings"] = {}
            state["collected_findings"][self.name] = {
                "status": "error",
                "error": str(e)
            }
            return state

    async def _extract_parameters_with_llm(self, query: str, state: AgentState = None) -> Dict[str, Optional[float]]:
        """
        Extract 7 parameters from natural language using LLM

        Supports:
        - Explicit numeric values ("N=90", "nitrogen 90", "pH 6.5")
        - Descriptive terms ("high nitrogen", "moderate rainfall", "acidic soil")
        - Hindi/Hinglish ("नाइट्रोजन अधिक है", "pH kam hai")
        - Regional info ("I live in Karnataka" → infer climate)

        Args:
            query: User's natural language query
            state: Agent state (optional, used to get detected location)

        Returns:
            Dict with extracted parameters (None for missing values)
        """
        # PHASE 1: Try regex extraction for explicit numeric parameters (fast path)
        regex_extracted = self._extract_parameters_with_regex(query)
        
        # PHASE 1.5: Try keyword-based heuristic extraction (robust fallback)
        keyword_extracted = self._extract_parameters_from_keywords(query)
        
        # Merge keyword findings into regex findings (Regex takes precedence for explicit numbers)
        # e.g. "clay soil with N=20" -> Regex N=20 overrides Keyword N=80
        combined_heuristics = {**keyword_extracted, **{k: v for k, v in regex_extracted.items() if v is not None}}

        # If heuristics found ALL parameters, skip LLM (saves ~500ms and quota)
        # We check against the count of needed parameters (7)
        if len(combined_heuristics) >= 7:
            logger.info(f"{self.name}: Heuristic extraction found sufficient parameters (fast path)")
            # Fill missing None values from empty template
            result = self._empty_params()
            result.update(combined_heuristics)
            return result

        # PHASE 2: Use LLM for natural language extraction
        # BUG FIX: Add location hint if location was detected by supervisor
        location_hint = ""
        if state and state.get("user_context", {}).get("location"):
            detected_location = state["user_context"]["location"]
            location_hint = f"""

**CRITICAL LOCATION INFORMATION:**
The location '{detected_location}' was detected in the user's query. You MUST infer climate parameters (temperature, humidity, rainfall) for this location if they are not explicitly provided in the query.
"""

        # MULTI-TURN CONTEXT: Build context from previous turns and extracted entities
        conversation_context = ""
        if state:
            user_context = state.get("user_context", {})
            previous_entities = []
            
            # Add location from context
            if user_context.get("location"):
                previous_entities.append(f"Location: {user_context['location']}")
            # Add soil type from context
            if user_context.get("soil_type"):
                previous_entities.append(f"Soil type: {user_context['soil_type']}")
            # Add crop from context (if user mentioned it earlier)
            if user_context.get("crop_type"):
                previous_entities.append(f"Crop: {user_context['crop_type']}")
            # Add any NPK from previous extraction
            if user_context.get("n_value"):
                previous_entities.append(f"N: {user_context['n_value']}")
            if user_context.get("p_value"):
                previous_entities.append(f"P: {user_context['p_value']}")
            if user_context.get("k_value"):
                previous_entities.append(f"K: {user_context['k_value']}")
            
            # Also check conversation_history for recent context
            conv_history = state.get("conversation_history", [])
            if conv_history and len(conv_history) > 0:
                # Get last user message for context
                recent_context = []
                for turn in conv_history[-2:]:  # Last 2 turns
                    if turn.get("role") == "user" and turn.get("content"):
                        recent_context.append(f"Previous: \"{turn['content'][:100]}\"")
                if recent_context:
                    previous_entities.extend(recent_context)
            
            if previous_entities:
                conversation_context = f"""

**CONVERSATION CONTEXT (from previous turns):**
{chr(10).join('- ' + e for e in previous_entities)}
Use this context when the current query is incomplete or refers to previously mentioned information.
"""

        prompt = f"""You are an expert agricultural assistant. Extract soil and climate parameters from the user's query.

User Query: "{query}"{location_hint}{conversation_context}

Extract the following 7 parameters if mentioned (return null if not found):

1. **N (Nitrogen)**: Nitrogen content in kg/ha (0-200)
   - Look for: "nitrogen", "N", "N=", "नाइट्रोजन"
   - Descriptive: "high nitrogen" → 100, "low nitrogen" → 20, "moderate" → 50

2. **P (Phosphorus)**: Phosphorus content in kg/ha (0-200)
   - Look for: "phosphorus", "P", "P=", "फास्फोरस"
   - Descriptive: "high P" → 80, "low P" → 20, "moderate" → 50

3. **K (Potassium)**: Potassium content in kg/ha (0-300)
   - Look for: "potassium", "K", "K=", "पोटैशियम"
   - Descriptive: "high potassium" → 150, "low K" → 30, "moderate" → 80

4. **temperature**: Average temperature in Celsius (-10 to 60)
   - Look for: "temperature", "temp", "temp=", "तापमान", "गर्मी", "ठंड"
   - Descriptive: "hot" → 35, "cold" → 10, "moderate" → 25, "warm" → 28

5. **humidity**: Relative humidity percentage (0-100)
   - Look for: "humidity", "humid", "humidity=", "आर्द्रता", "नमी"
   - Descriptive: "high humidity" → 80, "low humidity" → 40, "moderate" → 60

6. **ph**: Soil pH value (0-14, neutral=7)
   - Look for: "pH", "ph", "pH=", "acidity", "alkaline", "acidic", "neutral"
   - Descriptive: "acidic" → 5.5, "alkaline" → 8.0, "neutral" → 7.0

7. **rainfall**: Annual rainfall in mm (0-500)
   - Look for: "rainfall", "rain", "rain=", "precipitation", "बारिश", "वर्षा"
   - Descriptive: "high rainfall" → 250, "low rainfall" → 50, "moderate" → 120

**Regional Inference** (if location mentioned):
- "Karnataka": temperature~25°C, humidity~65%, rainfall~100mm
- "Punjab": temperature~23°C, humidity~60%, rainfall~70mm
- "Kerala": temperature~27°C, humidity~80%, rainfall~280mm
- "Rajasthan": temperature~30°C, humidity~40%, rainfall~40mm

**CRITICAL**: If explicit numeric values are in the query (like "N=90" or "temp=25"), extract EXACT values.

Return ONLY a valid JSON object with numeric values or null:
{{
  "N": <number or null>,
  "P": <number or null>,
  "K": <number or null>,
  "temperature": <number or null>,
  "humidity": <number or null>,
  "ph": <number or null>,
  "rainfall": <number or null>
}}

Examples:
Query: "N=90 P=40 K=40 temp=25 humidity=80 ph=6 rainfall=200"
Response: {{"N": 90, "P": 40, "K": 40, "temperature": 25, "humidity": 80, "ph": 6, "rainfall": 200}}

Query: "मेरी मिट्टी में nitrogen 90 है और pH 6.5 है"
Response: {{"N": 90, "P": null, "K": null, "temperature": null, "humidity": null, "ph": 6.5, "rainfall": null}}

Query: "I have high nitrogen soil in Kerala with moderate rainfall"
Response: {{"N": 100, "P": null, "K": null, "temperature": 27, "humidity": 80, "ph": null, "rainfall": 250}}

Query: "What crops grow well in Bangalore?"
Response: {{"N": null, "P": null, "K": null, "temperature": 25, "humidity": 65, "ph": null, "rainfall": 100}}

Query: "Best crops to grow in Mumbai?"
Response: {{"N": null, "P": null, "K": null, "temperature": 27, "humidity": 75, "ph": null, "rainfall": 200}}

Query: "I live in Delhi, what can I grow?"
Response: {{"N": null, "P": null, "K": null, "temperature": 25, "humidity": 60, "ph": null, "rainfall": 65}}

Query: "Crops for Pune region?"
Response: {{"N": null, "P": null, "K": null, "temperature": 25, "humidity": 60, "ph": null, "rainfall": 70}}

Query: "Best crop for my farm?"
Response: {{"N": null, "P": null, "K": null, "temperature": null, "humidity": null, "ph": null, "rainfall": null}}
"""

        try:
            # Call LLM (using generate_answer which returns tuple)
            response, _ = self.generation_service.generate_answer(
                query=prompt,
                retrieved_chunks=[],
                max_tokens=300,
                temperature=0.0
            )

            # Strip markdown code blocks if present
            response_clean = response.strip()
            if response_clean.startswith("```json"):
                response_clean = response_clean[7:]
            if response_clean.startswith("```"):
                response_clean = response_clean[3:]
            if response_clean.endswith("```"):
                response_clean = response_clean[:-3]
            response_clean = response_clean.strip()

            # Extract JSON from response
            json_match = re.search(r'\{[^{}]*\}', response_clean, re.DOTALL)
            if not json_match:
                logger.warning(f"{self.name}: No JSON found in LLM response, using heuristics fallback")
                # Fallback: Use combined heuristics (Regex + Keywords)
                result = self._empty_params()
                result.update(combined_heuristics)
                return result

            params = json.loads(json_match.group())

            # Convert None strings to actual None
            for key in params:
                if params[key] == "null" or params[key] == "None":
                    params[key] = None
                elif params[key] is not None:
                    try:
                        params[key] = float(params[key])
                    except (ValueError, TypeError):
                        params[key] = None

            # Merge with regex extracted values (LLM takes precedence only if it found a value)
            for key, value in params.items():
                if value is None and regex_extracted.get(key) is not None:
                    params[key] = regex_extracted[key]
                    logger.info(f"{self.name}: Used regex value for {key}={regex_extracted[key]}")

            return params

        except json.JSONDecodeError as e:
            logger.error(f"{self.name}: Failed to parse LLM JSON: {e}, using heuristics fallback")
            result = self._empty_params()
            result.update(combined_heuristics)
            return result
        except Exception as e:
            logger.error(f"{self.name}: LLM extraction failed: {e}, using heuristics fallback")
            result = self._empty_params()
            result.update(combined_heuristics)
            return result

    def _extract_parameters_from_keywords(self, query: str) -> Dict[str, float]:
        """
        Extract parameters based on keywords (Heuristic Fallback)
        
        Maps descriptive terms (clay, sandy, heavy rain) to approximate NPK/Climate values.
        This provides robustness when LLM rate limits are hit.
        
        Args:
            query: User query
            
        Returns:
            Dict of extracted numeric parameters
        """
        extracted = {}
        q = query.lower()
        
        # Soil Types
        if "clay" in q:
            # Clay holds water and nutrients well. Good for Rice/Jute.
            extracted.update({"N": 80, "P": 40, "K": 40, "ph": 6.0})
        elif "sandy" in q:
            # Sandy drains water fast, low nutrients. Good for Maize/Melons.
            extracted.update({"N": 20, "P": 20, "K": 20, "ph": 6.5, "rainfall": 50, "humidity": 40})
        elif "black" in q or "black soil" in q:
            # Black soil (Cotton soil). Rich in K, Ca, Mg.
            extracted.update({"N": 60, "P": 40, "K": 80, "ph": 7.5})
        elif "red" in q or "red soil" in q:
            # Red soil. Iron rich, often acidic.
            extracted.update({"N": 40, "P": 30, "K": 30, "ph": 5.5})
        elif "loam" in q:
            # Balanced soil.
            extracted.update({"N": 60, "P": 50, "K": 50})
            
        # Climate Conditions
        if "heavy rain" in q or "monsoon" in q or "flood" in q or "wet" in q:
            extracted["rainfall"] = 250
            extracted["humidity"] = 85
        elif "dry" in q or "desert" in q or "arid" in q:
            extracted["rainfall"] = 20
            extracted["humidity"] = 30
            if "temperature" not in extracted:
                extracted["temperature"] = 35 # Assume hot unless specified
                
        if "hot" in q or "summer" in q:
            extracted["temperature"] = 32
        elif "cold" in q or "winter" in q:
            extracted["temperature"] = 15
        elif "humid" in q:
            extracted["humidity"] = 80
            
        # Specific Crop Hints (Self-reinforcing logic)
        # If user asks about 'growing rice', give them rice-friendly params
        # This helps the ML model confirm the user's intent even if params are vague
        if "rice" in q or "paddy" in q:
            extracted.update({"N": 80, "P": 40, "K": 40, "rainfall": 200, "temperature": 25})
        elif "cotton" in q:
            extracted.update({"N": 120, "P": 40, "K": 20, "rainfall": 80, "temperature": 30})
        elif "maize" in q or "corn" in q:
            extracted.update({"N": 80, "P": 40, "K": 20, "rainfall": 100})
        elif "fruit" in q or "fruits" in q:
            # Generic fruit params (often moderate N, P, K)
            extracted.update({"N": 40, "P": 40, "K": 60})
            
        logger.info(f"{self.name}: Keyword heuristics extracted: {extracted}")
        return extracted


    def _extract_parameters_with_regex(self, query: str) -> Dict[str, Optional[float]]:
        """
        Extract explicit numeric parameters using regex (fast path, <5ms)

        Handles patterns like:
        - "N=90", "N = 90", "nitrogen=90"
        - "P=40", "phosphorus=40"
        - "temp=25", "temperature=25"
        - "ph=6.5", "pH=6.5"

        Args:
            query: User query with potential numeric parameters

        Returns:
            Dict with extracted values (None for not found)
        """
        extracted = {
            "N": None,
            "P": None,
            "K": None,
            "temperature": None,
            "humidity": None,
            "ph": None,
            "rainfall": None
        }

        # Patterns for each parameter
        patterns = {
            "N": r'(?:N|nitrogen)\s*[=:]\s*([0-9]+(?:\.[0-9]+)?)',
            "P": r'(?:P|phosphorus|phosphorous)\s*[=:]\s*([0-9]+(?:\.[0-9]+)?)',
            "K": r'(?:K|potassium)\s*[=:]\s*([0-9]+(?:\.[0-9]+)?)',
            "temperature": r'(?:temp|temperature)\s*[=:]\s*([0-9]+(?:\.[0-9]+)?)',
            "humidity": r'(?:humidity|humid)\s*[=:]\s*([0-9]+(?:\.[0-9]+)?)',
            "ph": r'(?:pH|ph)\s*[=:]\s*([0-9]+(?:\.[0-9]+)?)',
            "rainfall": r'(?:rainfall|rain)\s*[=:]\s*([0-9]+(?:\.[0-9]+)?)'
        }

        for param_name, pattern in patterns.items():
            match = re.search(pattern, query, re.IGNORECASE)
            if match:
                try:
                    value = float(match.group(1))
                    extracted[param_name] = value
                    logger.info(f"{self.name}: Regex extracted {param_name}={value}")
                except (ValueError, AttributeError):
                    pass

        return extracted

    def _empty_params(self) -> Dict[str, None]:
        """Return empty parameters dict"""
        return {
            "N": None,
            "P": None,
            "K": None,
            "temperature": None,
            "humidity": None,
            "ph": None,
            "rainfall": None
        }

    def _apply_defaults_with_tracking(
        self,
        extracted_params: Dict[str, Optional[float]]
    ) -> tuple[Dict[str, float], list[str]]:
        """
        Apply default values for missing parameters and track which defaults were used

        Args:
            extracted_params: Parameters extracted from query (may have None values)

        Returns:
            Tuple of (complete_params, defaults_used)
            - complete_params: Dict with all parameters filled
            - defaults_used: List of parameter names that used defaults
        """
        complete_params = {}
        defaults_used = []

        for param_name in ["N", "P", "K", "temperature", "humidity", "ph", "rainfall"]:
            value = extracted_params.get(param_name)

            if value is None:
                # Use default value
                complete_params[param_name] = DEFAULT_VALUES[param_name]
                defaults_used.append(param_name)
            else:
                complete_params[param_name] = value

        return complete_params, defaults_used

    def _apply_regional_climate(
        self,
        state: AgentState,
        extracted_params: Dict[str, Optional[float]]
    ) -> Dict[str, Optional[float]]:
        """
        Apply regional climate defaults based on location (CRITICAL BUG FIX)

        PRIORITY ORDER for filling missing parameters:
        1. Explicit user-provided values (from query) → KEEP these
        2. Regional climate values (if location known) → Use for missing params
        3. Generic defaults → Only use if no location and no explicit value

        Args:
            state: Agent state with user_context
            extracted_params: Parameters extracted from query (may have None values)

        Returns:
            Parameters with regional climate applied for missing values

        Example:
            Query: "Best crops in Bangalore"
            extracted_params: {N: None, P: None, ..., temperature: None, ...}
            → Loads Bangalore climate → {temperature: 25, humidity: 65, rainfall: 100}
            → Returns params with Bangalore's climate for missing fields
        """
        # Check for location in user_context (set by supervisor)
        location = state.get("user_context", {}).get("location")

        if not location:
            # No location found - will use generic defaults later
            logger.info(f"{self.name}: No location found in user_context, will use generic defaults")
            return extracted_params

        # Get regional climate for this location
        regional_climate = get_climate_for_location(location)

        if not regional_climate:
            # Location not in database - will use generic defaults
            logger.warning(f"{self.name}: Location '{location}' not in regional climate database")
            return extracted_params

        # Apply regional climate ONLY for missing parameters
        # IMPORTANT: User-provided values take precedence!
        climate_applied = []
        updated_params = extracted_params.copy()

        # Map climate fields to parameter names
        climate_mapping = {
            "temperature": "temperature",
            "humidity": "humidity",
            "rainfall": "rainfall"
        }

        for param_name, climate_key in climate_mapping.items():
            # Only apply if parameter is missing (None)
            if extracted_params.get(param_name) is None:
                climate_value = regional_climate.get(climate_key)
                if climate_value is not None:
                    updated_params[param_name] = float(climate_value)
                    climate_applied.append(f"{param_name}={climate_value}")

        if climate_applied:
            logger.info(
                f"{self.name}: ✅ Using regional climate for {location}: {', '.join(climate_applied)}"
            )
            logger.info(
                f"{self.name}: Regional climate defaults: "
                f"temp={regional_climate.get('temperature')}°C, "
                f"humidity={regional_climate.get('humidity')}%, "
                f"rainfall={regional_climate.get('rainfall')}mm"
            )
        else:
            logger.info(f"{self.name}: Regional climate for {location} found but all params already provided")

        return updated_params

    def _validate_parameters(self, params: Dict[str, float]) -> list[str]:
        """
        Validate parameter ranges

        Args:
            params: Complete parameters dict

        Returns:
            List of validation error messages (empty if valid)
        """
        errors = []

        for param_name, (min_val, max_val) in PARAMETER_RANGES.items():
            value = params.get(param_name)

            if value is None:
                continue  # Skip validation for None (shouldn't happen after applying defaults)

            if value < min_val or value > max_val:
                errors.append(
                    f"{param_name} value {value} is out of valid range [{min_val}, {max_val}]"
                )

        return errors

    def _detect_multi_crop_request(self, query: str) -> int:
        """
        Detect if user is asking for multiple crop recommendations.
        
        Patterns detected:
        - "5 best crops for Punjab"
        - "top 3 crops for my area"
        - "suggest multiple crops"
        - "several crop options"
        - "list of crops"
        
        Returns:
            Number of crops requested (1 if single crop, 3-5 if multiple)
        """
        query_lower = query.lower()
        
        # Pattern 1: Explicit number (e.g., "5 best crops", "top 3 crops")
        import re
        number_match = re.search(r'(?:top|best|suggest|recommend)\s*(\d+)\s*(?:crops?|options?)', query_lower)
        if number_match:
            count = int(number_match.group(1))
            return min(count, 10)  # Cap at 10
        
        # Pattern 2: Reverse order (e.g., "5 crops", "3 crop options")
        reverse_match = re.search(r'(\d+)\s*(?:best|top)?\s*crops?', query_lower)
        if reverse_match:
            count = int(reverse_match.group(1))
            return min(count, 10)
        
        # Pattern 3: Keywords for multiple (default to 5)
        multi_keywords = ['multiple', 'several', 'few', 'some', 'list of', 'various', 'different']
        if any(kw in query_lower for kw in multi_keywords):
            return 5
        
        # Default: single crop
        return 1

    def _detect_user_crop_preference(self, query: str) -> Optional[str]:
        """
        Detect if user explicitly stated which crop they want to grow (BUG FIX #8)

        Handles patterns like:
        - "I want to grow wheat"
        - "I have sandy soil and want to grow wheat"
        - "Planning to plant rice"
        - "मैं गेहूं उगाना चाहता हूं" (I want to grow wheat in Hindi)

        Args:
            query: User's natural language query

        Returns:
            Crop name if detected, None otherwise
        """
        # Common crop names (English)
        crops = [
            "wheat", "rice", "paddy", "maize", "corn", "cotton", "sugarcane",
            "potato", "tomato", "onion", "soybean", "pulses", "chickpea",
            "barley", "millet", "bajra", "jowar", "ragi", "groundnut",
            "sunflower", "mustard", "sesame", "jute", "tea", "coffee",
            "banana", "mango", "apple", "grapes", "orange", "coconut"
        ]

        # Hindi to English mapping
        hindi_crops = {
            "गेहूं": "wheat", "गेंहू": "wheat",
            "धान": "rice", "चावल": "rice",
            "मक्का": "maize", "भुट्टा": "maize",
            "कपास": "cotton",
            "गन्ना": "sugarcane",
            "आलू": "potato",
            "टमाटर": "tomato",
            "प्याज": "onion"
        }

        query_lower = query.lower()

        # Pattern 1: "want to grow X", "planning to plant X", "growing X"
        intent_patterns = [
            r'(?:want|plan|planning|intend|like)\s+to\s+(?:grow|plant|cultivate)\s+(\w+)',
            r'(?:growing|planting|cultivating)\s+(\w+)',
            r'(?:i\s+am|i\'m)\s+(?:growing|planting)\s+(\w+)',
            r'for\s+(\w+)\s+crop',
            r'(\w+)\s+crop',
        ]

        for pattern in intent_patterns:
            match = re.search(pattern, query_lower)
            if match:
                potential_crop = match.group(1).strip()
                # Check if it's a known crop
                if potential_crop in crops:
                    logger.info(f"{self.name}: Detected user preference via pattern: {potential_crop}")
                    return potential_crop

        # Pattern 2: Check for Hindi crop names
        for hindi_crop, english_crop in hindi_crops.items():
            if hindi_crop in query:
                logger.info(f"{self.name}: Detected Hindi crop preference: {hindi_crop} → {english_crop}")
                return english_crop

        # Pattern 3: Direct crop mention at end of sentence (e.g., "I have sandy soil for wheat")
        for crop in crops:
            # Look for crop name with common surrounding words
            crop_patterns = [
                rf'\b{crop}\b',  # Word boundary match
            ]
            for crop_pattern in crop_patterns:
                if re.search(crop_pattern, query_lower):
                    # Check if it's in a preference context (not just mentioned in passing)
                    preference_indicators = ["want", "grow", "plant", "cultivate", "for", "with"]
                    if any(indicator in query_lower for indicator in preference_indicators):
                        logger.info(f"{self.name}: Detected crop preference: {crop}")
                        return crop

        return None

    def health_check(self) -> Dict[str, Any]:
        """
        Check health of crop agent and its dependencies

        Returns:
            Health status dictionary with service availability
        """
        status = super().health_check()

        # Check generation service availability
        status["generation_service_available"] = self.generation_service is not None

        # Check if tool callable is configured
        status["tool_configured"] = self.tool_callable is not None

        # Overall health
        all_ok = (
            status["generation_service_available"]
            and status["tool_configured"]
        )
        status["status"] = "healthy" if all_ok else "degraded"

        return status
