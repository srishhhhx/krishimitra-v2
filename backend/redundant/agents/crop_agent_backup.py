"""
Crop Recommendation Agent

This agent handles crop recommendation queries using the Naive Bayes model
through the crop_recommendation_tool. It extracts 7 parameters from natural
language (N, P, K, temperature, humidity, pH, rainfall), applies intelligent
defaults, and executes the prediction tool.

Supports Hindi + Hinglish with parameter extraction and normalization.

Key Features:
- LLM-based extraction of 7 soil/climate parameters
- Smart defaults for missing values
- Multi-turn clarification (future optimization)
- Hindi/Hinglish language support
"""

import json
import re
from typing import Dict, Any, Optional

from agents.base import ToolAgent, track_latency
from schemas.agents import AgentState
from tools.crop_recommendation_tool import recommend_crop, apply_defaults, DEFAULT_VALUES
from core.logging import get_logger

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
    Agent for crop recommendation using Naive Bayes model.

    This agent:
    1. Extracts 7 parameters from natural language using LLM
    2. Applies intelligent defaults for missing non-critical parameters
    3. Validates parameter ranges
    4. Executes crop recommendation tool
    5. Updates state with results

    Parameters:
        N (float): Nitrogen content (kg/ha) - default: 50.0
        P (float): Phosphorus content (kg/ha) - default: 50.0
        K (float): Potassium content (kg/ha) - default: 50.0
        temperature (float): Temperature (°C) - default: 25.0
        humidity (float): Humidity (%) - default: 65.0
        ph (float): Soil pH - default: 6.5
        rainfall (float): Rainfall (mm) - default: 100.0

    Note:
        For MVP, we apply defaults for all missing parameters.
        Future optimization: Call WeatherAgent for temp/humidity/rainfall,
        and SoilAgent for N/P/K/pH based on user location.
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
        Execute crop recommendation workflow

        Workflow:
        1. Extract 7 parameters from user_query using LLM
        2. Apply defaults for missing parameters
        3. Validate parameter ranges
        4. Execute crop recommendation tool
        5. Update state with results

        Args:
            state: Current agent state with user_query

        Returns:
            Updated state with crop_output containing:
                - recommended_crop: Primary crop recommendation
                - confidence_percentage: Confidence score (0-100)
                - alternatives: List of alternative crops
                - parameters_used: Echo of parameters (for transparency)
                - defaults_applied: Which defaults were used (for user awareness)
        """
        try:
            query = state.get("user_query", "")
            if not query:
                state["error"] = f"{self.name}: No query provided"
                return state

            logger.info(f"{self.name}: Processing query: {query[:100]}...")

            # Phase 1: Extract parameters from natural language using LLM
            extracted_params = await self._extract_parameters_with_llm(query)
            logger.info(f"{self.name}: Extracted parameters: {extracted_params}")

            # Phase 2: Apply defaults for missing parameters
            complete_params, defaults_used = self._apply_defaults_with_tracking(extracted_params)

            if defaults_used:
                logger.info(f"{self.name}: Applied defaults for: {defaults_used}")
            else:
                logger.info(f"{self.name}: All parameters provided by user")

            # Phase 3: Validate parameters
            validation_errors = self._validate_parameters(complete_params)
            if validation_errors:
                state["error"] = f"{self.name}: {'; '.join(validation_errors)}"
                state["crop_output"] = {
                    "error": "; ".join(validation_errors),
                    "needs_clarification": True,
                    "extracted_params": extracted_params
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
                state["error"] = f"{self.name}: {result['error']}"
                state["crop_output"] = result
                return state

            # Phase 6: Enhance result with defaults transparency
            result["defaults_applied"] = defaults_used
            result["metadata"]["defaults_used"] = bool(defaults_used)

            # Phase 7: Update state
            state["crop_output"] = result
            logger.info(
                f"{self.name}: Recommended crop: {result.get('recommended_crop')} "
                f"(confidence: {result.get('confidence_percentage', 0):.2f}%)"
            )

            # Phase 8: Track agent execution
            if "executed_agents" not in state:
                state["executed_agents"] = []
            state["executed_agents"].append(self.name)

            return state

        except Exception as e:
            logger.error(f"{self.name} failed: {e}", exc_info=True)
            state["error"] = f"{self.name}: {str(e)}"
            state["crop_output"] = {
                "error": str(e),
                "recommended_crop": None
            }
            return state

    async def _extract_parameters_with_llm(self, query: str) -> Dict[str, Optional[float]]:
        """
        Extract 7 parameters from natural language using LLM

        Supports:
        - Explicit numeric values ("N=90", "nitrogen 90", "pH 6.5")
        - Descriptive terms ("high nitrogen", "moderate rainfall", "acidic soil")
        - Hindi/Hinglish ("नाइट्रोजन अधिक है", "pH kam hai")
        - Regional info ("I live in Karnataka" → infer climate)

        Args:
            query: User's natural language query

        Returns:
            Dict with extracted parameters (None for missing values)
        """
        prompt = f"""You are an expert agricultural assistant. Extract soil and climate parameters from the user's query.

User Query: "{query}"

Extract the following 7 parameters if mentioned (return null if not found):

1. **N (Nitrogen)**: Nitrogen content in kg/ha (0-200)
   - Look for: "nitrogen", "N", "नाइट्रोजन"
   - Descriptive: "high nitrogen" → 100, "low nitrogen" → 20, "moderate" → 50

2. **P (Phosphorus)**: Phosphorus content in kg/ha (0-200)
   - Look for: "phosphorus", "P", "फास्फोरस"
   - Descriptive: "high P" → 80, "low P" → 20, "moderate" → 50

3. **K (Potassium)**: Potassium content in kg/ha (0-300)
   - Look for: "potassium", "K", "पोटैशियम"
   - Descriptive: "high potassium" → 150, "low K" → 30, "moderate" → 80

4. **temperature**: Average temperature in Celsius (-10 to 60)
   - Look for: "temperature", "temp", "तापमान", "गर्मी", "ठंड"
   - Descriptive: "hot" → 35, "cold" → 10, "moderate" → 25, "warm" → 28

5. **humidity**: Relative humidity percentage (0-100)
   - Look for: "humidity", "humid", "आर्द्रता", "नमी"
   - Descriptive: "high humidity" → 80, "low humidity" → 40, "moderate" → 60

6. **ph**: Soil pH value (0-14, neutral=7)
   - Look for: "pH", "acidity", "alkaline", "acidic", "neutral"
   - Descriptive: "acidic" → 5.5, "alkaline" → 8.0, "neutral" → 7.0

7. **rainfall**: Annual rainfall in mm (0-500)
   - Look for: "rainfall", "rain", "precipitation", "बारिश", "वर्षा"
   - Descriptive: "high rainfall" → 250, "low rainfall" → 50, "moderate" → 120

**Regional Inference** (if location mentioned):
- "Karnataka": temperature~25°C, humidity~65%, rainfall~100mm
- "Punjab": temperature~23°C, humidity~60%, rainfall~70mm
- "Kerala": temperature~27°C, humidity~80%, rainfall~280mm
- "Rajasthan": temperature~30°C, humidity~40%, rainfall~40mm

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
Query: "मेरी मिट्टी में nitrogen 90 है और pH 6.5 है"
Response: {{"N": 90, "P": null, "K": null, "temperature": null, "humidity": null, "ph": 6.5, "rainfall": null}}

Query: "I have high nitrogen soil in Kerala with moderate rainfall"
Response: {{"N": 100, "P": null, "K": null, "temperature": 27, "humidity": 80, "ph": null, "rainfall": 250}}

Query: "Best crop for my farm?"
Response: {{"N": null, "P": null, "K": null, "temperature": null, "humidity": null, "ph": null, "rainfall": null}}
"""

        try:
            # Call LLM (using generate_answer which returns tuple)
            response, _ = self.generation_service.generate_answer(
                query=prompt,
                retrieved_chunks=[],
                max_tokens=300
            )

            # Extract JSON from response
            json_match = re.search(r'\{[^{}]*\}', response, re.DOTALL)
            if not json_match:
                logger.warning(f"{self.name}: No JSON found in LLM response")
                return self._empty_params()

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

            return params

        except json.JSONDecodeError as e:
            logger.error(f"{self.name}: Failed to parse LLM JSON: {e}")
            return self._empty_params()
        except Exception as e:
            logger.error(f"{self.name}: LLM extraction failed: {e}")
            return self._empty_params()

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
        if not status["generation_service_available"]:
            status["status"] = "degraded"
        elif not status["tool_configured"]:
            status["status"] = "degraded"

        return status
