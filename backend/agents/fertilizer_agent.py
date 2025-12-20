"""
Fertilizer Recommendation Agent (Refactored with Clarification Support)

This agent handles fertilizer recommendation queries using the XGBoost
model through the fertilizer_tool.

**Multi-Turn Conversation Support:**
- Uses BaseAgent._check_required_fields() for clarification
- Agents NEVER talk to users directly
- Supervisor handles all clarification

Features:
- Extracts 8 parameters from natural language using LLM
- Fast-path Hindi extraction using regex (bypasses LLM, <5ms)
- Hindi/Hinglish normalization
- Applies defaults for optional parameters
- Validates and executes prediction tool

Required Parameters:
    - soil_type: sandy/loamy/black/red/clayey (REQUIRED)
    - crop_type: wheat/rice/maize/cotton/etc. (REQUIRED)

Optional Parameters (with defaults):
    - temperature: default 25.0°C
    - humidity: default 60.0%
    - moisture: default 50.0%
    - nitrogen: default 40.0 kg/ha
    - phosphorous: default 30.0 kg/ha
    - potassium: default 30.0 kg/ha
"""
import json
import re
from typing import Dict, Any, List

from agents.base import ToolAgent, track_latency
from schemas.agents import AgentState
from schemas.supervisor import ResolutionStrategy
from tools.fertilizer_tool import predict_fertilizer_core
from core.logging import get_logger

logger = get_logger(__name__)


# ============================================================================
# Hindi to English Normalization for Parameter Extraction
# ============================================================================

HINDI_TO_ENGLISH_CROP = {
    "गेहूं": "wheat",
    "गेंहू": "wheat",
    "धान": "paddy",
    "चावल": "rice",
    "मक्का": "maize",
    "भुट्टा": "maize",
    "कौर्न": "maize",
    "चना": "pulses",
    "अरहर": "pulses",
    "सोयाबीन": "oil seeds",
    "सरसों": "oil seeds",
    "कपास": "cotton",
    "गन्ना": "sugarcane",
    "तंबाकू": "tobacco",
    "जौ": "barley",
    "बाजरा": "millets",
    "मूंगफली": "ground nuts",
}

HINDI_TO_ENGLISH_SOIL = {
    "काली मिट्टी": "black",
    "काली": "black",
    "लोमी मिट्टी": "loamy",
    "लोमी": "loamy",
    "बलुई मिट्टी": "sandy",
    "बलुई": "sandy",
    "रेतीली मिट्टी": "sandy",
    "रेतीली": "sandy",
    "लाल मिट्टी": "red",
    "लाल": "red",
    "चिकनी मिट्टी": "clayey",
    "चिकनी": "clayey",
}

# Fast-path regex patterns for Hindi extraction
HINDI_SOIL_PATTERNS = [
    r"(काली|लोमी|बलुई|रेतीली|लाल|चिकनी)\s*(मिट्टी)?",
]

HINDI_CROP_PATTERNS = [
    r"(गेहूं|गेंहू|धान|चावल|मक्का|भुट्टा|कौर्न|चना|अरहर|सोयाबीन|सरसों|कपास|गन्ना|तंबाकू|जौ|बाजरा|मूंगफली)",
]

# ============================================================================
# Field Metadata for Clarification (BaseAgent Integration)
# ============================================================================

FIELD_METADATA = {
    "soil_type": {
        "type": "enum",
        "description": "Your soil type (sandy/loamy/black/red/clayey)",
        "allowed_values": ["sandy", "loamy", "black", "red", "clayey"],
        "resolution_strategy": ResolutionStrategy.NORMALIZE
    },
    "crop_type": {
        "type": "string",
        "description": "Which crop are you growing? (wheat/rice/maize/cotton/sugarcane/etc.)",
        "resolution_strategy": ResolutionStrategy.NORMALIZE
    },
    "temperature": {
        "type": "float",
        "description": "Average temperature in °C (optional, default: 25.0°C)",
        "resolution_strategy": ResolutionStrategy.REPLACE
    },
    "humidity": {
        "type": "float",
        "description": "Average humidity in % (optional, default: 60.0%)",
        "resolution_strategy": ResolutionStrategy.REPLACE
    },
    "moisture": {
        "type": "float",
        "description": "Soil moisture in % (optional, default: 50.0%)",
        "resolution_strategy": ResolutionStrategy.REPLACE
    },
    "nitrogen": {
        "type": "float",
        "description": "Nitrogen content in kg/ha (optional, default: 40.0)",
        "resolution_strategy": ResolutionStrategy.REPLACE
    },
    "phosphorous": {
        "type": "float",
        "description": "Phosphorous content in kg/ha (optional, default: 30.0)",
        "resolution_strategy": ResolutionStrategy.REPLACE
    },
    "potassium": {
        "type": "float",
        "description": "Potassium content in kg/ha (optional, default: 30.0)",
        "resolution_strategy": ResolutionStrategy.REPLACE
    }
}


class FertilizerAgent(ToolAgent):
    """
    Agent for fertilizer recommendation using XGBoost model

    This agent:
    1. Extracts 8 parameters from natural language using LLM
    2. Checks for missing critical parameters (soil_type, crop_type)
    3. Asks clarifying questions if critical params missing
    4. Applies defaults for optional parameters (temp, humidity, etc.)
    5. Executes fertilizer prediction tool
    6. Updates state with results

    Critical Parameters (required):
        - soil_type: sandy/loamy/black/red/clayey
        - crop_type: wheat/rice/maize/cotton/etc.

    Optional Parameters (have defaults):
        - temperature: default 25.0°C
        - humidity: default 60.0%
        - moisture: default 50.0%
        - nitrogen: default 40.0 kg/ha
        - phosphorous: default 30.0 kg/ha
        - potassium: default 30.0 kg/ha
    """

    def __init__(self, generation_service):
        """
        Initialize Fertilizer Agent

        Args:
            generation_service: Service for LLM generation (used for parameter extraction)
        """
        super().__init__(
            name="fertilizer_agent",
            description="Provides fertilizer recommendations based on soil, crop, and environmental conditions",
            tool_callable=predict_fertilizer_core
        )
        self.generation_service = generation_service

    @track_latency("fertilizer_agent")
    async def run(self, state: AgentState) -> AgentState:
        """
        Execute fertilizer recommendation workflow (Orchestrator V2 Pattern)

        WORKFLOW (Multi-Turn Conversation):
        1. Extract existing fields from state (user_context + previous turns)
        2. Extract parameters from current query (Hindi fast-path → LLM fallback)
        3. Normalize Hindi params to English
        4. Check for missing REQUIRED fields (soil_type, crop_type)
        5. If missing: Return needs_clarification status
        6. If complete: Apply defaults for optional fields and execute tool

        Args:
            state: Current agent state with user_query and user_context

        Returns:
            Updated state with collected_findings["fertilizer_agent"] containing:
                - status: "success" | "error" | "needs_clarification"
                - data: Fertilizer recommendation (if success)
                - error: Error message (if error)
                - clarification_question: Question for user (if needs_clarification)
        """
        # Initialize collected_findings if needed
        if "collected_findings" not in state:
            state["collected_findings"] = {}

        try:
            query = state.get("user_query", "")
            if not query:
                state["collected_findings"]["fertilizer_agent"] = {
                    "status": "error",
                    "error": "No query provided"
                }
                return state

            logger.info(f"{self.name}: Processing query: {query[:100]}...")

            # Phase 1: Extract existing fields from state (user_context, previous clarifications)
            field_names = ["soil_type", "crop_type", "temperature", "humidity",
                          "moisture", "nitrogen", "phosphorous", "potassium"]
            existing_fields = self._extract_input_from_state(state, field_names)
            logger.info(f"{self.name}: Existing fields from state: {existing_fields}")

            # Phase 2: Fast-path extraction for Hindi (regex-based, <5ms)
            fast_extracted = self._fast_extract_hindi_params(query)

            # Phase 3: LLM extraction (if fast-path incomplete)
            if fast_extracted.get("soil_type") and fast_extracted.get("crop_type"):
                logger.info(f"{self.name}: Fast-path extraction succeeded (Hindi): {fast_extracted}")
                extracted_from_query = fast_extracted
            else:
                extracted_from_query = await self._extract_parameters_with_llm(query)
                logger.info(f"{self.name}: LLM extraction: {extracted_from_query}")

                # Merge fast-extracted params (fast-path takes precedence)
                extracted_from_query = {**extracted_from_query, **fast_extracted}

            # Phase 4: Normalize Hindi crop/soil to English
            extracted_from_query = self._normalize_hindi_params(extracted_from_query)
            logger.info(f"{self.name}: After normalization: {extracted_from_query}")

            # Phase 5: Merge existing fields with newly extracted (only non-None new values override)
            merged_input = existing_fields.copy()
            for key, value in extracted_from_query.items():
                # Only override existing values if the new value is not None
                if value is not None:
                    merged_input[key] = value
            logger.info(f"{self.name}: Merged input: {merged_input}")

            # Phase 6: Check for missing REQUIRED fields (BaseAgent pattern)
            clarification_req = self._check_required_fields(
                input_data=merged_input,
                required_fields=["soil_type", "crop_type"],
                field_metadata=FIELD_METADATA
            )

            if clarification_req:
                # Missing required fields - return needs_clarification status
                logger.info(f"{self.name}: Missing fields {clarification_req['requested_fields']}, requesting clarification")

                # Build clarification question from requested fields
                missing_fields = clarification_req['requested_fields']
                questions = []
                for field in missing_fields:
                    if field == "soil_type":
                        questions.append("What type of soil do you have? (sandy/loamy/black/red/clayey)")
                    elif field == "crop_type":
                        questions.append("Which crop are you growing? (wheat/rice/maize/cotton/sugarcane/etc.)")

                clarification_question = " ".join(questions)

                state["collected_findings"]["fertilizer_agent"] = {
                    "status": "needs_clarification",
                    "error": f"Missing required parameters: {', '.join(missing_fields)}",
                    "clarification_question": clarification_question,
                    "requested_fields": missing_fields,
                    "extracted_params": merged_input
                }

                # Add to executed agents
                if state.get("executed_agents") is None:
                    state["executed_agents"] = []
                state["executed_agents"].append(self.name)

                # Return early - Supervisor will handle user interaction
                return state

            # Phase 7: All required fields present - apply defaults for optional fields
            complete_params = self._apply_defaults(merged_input)
            logger.info(f"{self.name}: Complete parameters after defaults: {complete_params}")

            # Phase 8: Execute tool
            result = self.tool_callable(**complete_params)

            # Phase 9: Check for tool errors
            if "error" in result:
                logger.warning(f"{self.name}: Tool execution failed: {result['error']}")
                state["collected_findings"]["fertilizer_agent"] = {
                    "status": "error",
                    "error": result['error'],
                    "input_parameters": complete_params
                }
            else:
                logger.info(
                    f"{self.name}: Recommended {result['fertilizer_name']} "
                    f"({result['npk_ratio']}) for {complete_params['crop_type']}"
                )
                state["collected_findings"]["fertilizer_agent"] = {
                    "status": "success",
                    "data": result
                }

            # Add to executed agents
            if state.get("executed_agents") is None:
                state["executed_agents"] = []
            state["executed_agents"].append(self.name)

            return state

        except Exception as e:
            logger.error(f"{self.name} failed: {e}", exc_info=True)
            state["collected_findings"]["fertilizer_agent"] = {
                "status": "error",
                "error": str(e)
            }
            return state

    async def _extract_parameters_with_llm(self, query: str) -> Dict[str, Any]:
        """
        Extract 8 fertilizer parameters from natural language query using LLM

        Uses the generation service to parse user query and extract parameters
        in structured JSON format.

        Args:
            query: User's natural language query

        Returns:
            Dictionary with 8 parameters (null for missing):
                {
                    "temperature": float or None,
                    "humidity": float or None,
                    "moisture": float or None,
                    "soil_type": str or None,
                    "crop_type": str or None,
                    "nitrogen": float or None,
                    "phosphorous": float or None,
                    "potassium": float or None
                }
        """
        extraction_prompt = f"""
Extract fertilizer recommendation parameters from this query:
"{query}"

Return ONLY a JSON object with these fields (use null for missing):
{{
    "temperature": <float or null>,
    "humidity": <float or null>,
    "moisture": <float or null>,
    "soil_type": <"sandy"|"loamy"|"black"|"red"|"clayey" or null>,
    "crop_type": <crop name string or null>,
    "nitrogen": <float or null>,
    "phosphorous": <float or null>,
    "potassium": <float or null>
}}

Examples:
Query: "Sandy soil, wheat, 25°C, humidity 60%, N=40, P=50, K=30"
Output: {{"temperature": 25.0, "humidity": 60.0, "moisture": null, "soil_type": "sandy", "crop_type": "wheat", "nitrogen": 40.0, "phosphorous": 50.0, "potassium": 30.0}}

Query: "Which fertilizer for rice?"
Output: {{"temperature": null, "humidity": null, "moisture": null, "soil_type": null, "crop_type": "rice", "nitrogen": null, "phosphorous": null, "potassium": null}}

Query: "I have loamy soil and want to grow cotton. Soil test shows N=50, P=35, K=40"
Output: {{"temperature": null, "humidity": null, "moisture": null, "soil_type": "loamy", "crop_type": "cotton", "nitrogen": 50.0, "phosphorous": 35.0, "potassium": 40.0}}

Only extract explicitly mentioned info. Return JSON only, no explanations.
"""

        try:
            # Call generation service
            response, _ = self.generation_service.generate_answer(
                query=extraction_prompt,
                retrieved_chunks=[],
                max_tokens=200,
                temperature=0.0
            )

            # Parse JSON from response
            json_str = response.strip()

            # Handle markdown code blocks
            if "```json" in json_str:
                json_str = json_str.split("```json")[1].split("```")[0].strip()
            elif "```" in json_str:
                json_str = json_str.split("```")[1].split("```")[0].strip()

            # Remove any trailing text after closing brace
            brace_idx = json_str.rfind("}")
            if brace_idx != -1:
                json_str = json_str[:brace_idx + 1]

            extracted = json.loads(json_str)

            # Ensure all expected keys are present
            default_structure = {
                "temperature": None,
                "humidity": None,
                "moisture": None,
                "soil_type": None,
                "crop_type": None,
                "nitrogen": None,
                "phosphorous": None,
                "potassium": None
            }

            # Merge extracted with defaults (extracted takes precedence)
            result = {**default_structure, **extracted}

            logger.info(f"Successfully extracted parameters: {result}")
            return result

        except json.JSONDecodeError as e:
            logger.warning(f"JSON parse failed: {e}. Response: {response[:200]}")
            # Return empty structure on parse failure
            return {
                "temperature": None,
                "humidity": None,
                "moisture": None,
                "soil_type": None,
                "crop_type": None,
                "nitrogen": None,
                "phosphorous": None,
                "potassium": None
            }
        except Exception as e:
            logger.error(f"Parameter extraction failed: {e}", exc_info=True)
            # Return empty structure on any failure
            return {
                "temperature": None,
                "humidity": None,
                "moisture": None,
                "soil_type": None,
                "crop_type": None,
                "nitrogen": None,
                "phosphorous": None,
                "potassium": None
            }

    def _fast_extract_hindi_params(self, query: str) -> Dict[str, Any]:
        """
        Fast-path extraction for Hindi queries using regex patterns
        
        This bypasses LLM extraction for simple Hindi queries, reducing
        latency from ~500ms to <5ms.
        
        Args:
            query: User query (may contain Hindi)
            
        Returns:
            Dictionary with extracted soil_type and crop_type (if found)
        """
        extracted = {}
        
        # Extract Hindi soil type
        for pattern in HINDI_SOIL_PATTERNS:
            match = re.search(pattern, query)
            if match:
                hindi_soil = match.group(1)
                if hindi_soil in HINDI_TO_ENGLISH_SOIL:
                    extracted["soil_type"] = hindi_soil
                    logger.info(f"Fast-path: Found Hindi soil '{hindi_soil}'")
                    break
        
        # Extract Hindi crop type
        for pattern in HINDI_CROP_PATTERNS:
            match = re.search(pattern, query)
            if match:
                hindi_crop = match.group(1)
                if hindi_crop in HINDI_TO_ENGLISH_CROP:
                    extracted["crop_type"] = hindi_crop
                    logger.info(f"Fast-path: Found Hindi crop '{hindi_crop}'")
                    break
        
        return extracted
    
    def _normalize_hindi_params(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """
        Normalize Hindi crop and soil names to English

        Handles cases where LLM or fast-path extracted Hindi terms.
        Provides graceful fallback for unknown Hindi terms.
        Also strips whitespace from string values.

        Args:
            params: Parameter dictionary (may contain Hindi values)

        Returns:
            Parameter dictionary with normalized English values
        """
        normalized = params.copy()

        # Normalize crop_type
        if params.get("crop_type"):
            crop = params["crop_type"]
            if crop in HINDI_TO_ENGLISH_CROP:
                normalized["crop_type"] = HINDI_TO_ENGLISH_CROP[crop]
                logger.info(f"Normalized crop: {crop} → {normalized['crop_type']}")
            elif self._is_valid_english_crop(crop):
                # Valid English crop - strip and store clean value
                normalized["crop_type"] = crop.strip().lower()
            else:
                # Unknown crop - will trigger clarification
                logger.warning(f"Unknown crop name: {crop}")
                normalized["crop_type"] = None

        # Normalize soil_type
        if params.get("soil_type"):
            soil = params["soil_type"]
            if soil in HINDI_TO_ENGLISH_SOIL:
                normalized["soil_type"] = HINDI_TO_ENGLISH_SOIL[soil]
                logger.info(f"Normalized soil: {soil} → {normalized['soil_type']}")
            elif self._is_valid_english_soil(soil):
                # Valid English soil - strip and store clean value
                normalized["soil_type"] = soil.strip().lower()
            else:
                # Unknown soil - will trigger clarification
                logger.warning(f"Unknown soil type: {soil}")
                normalized["soil_type"] = None

        return normalized
    
    def _is_valid_english_crop(self, crop: str) -> bool:
        """Check if crop name is a valid English crop type"""
        valid_crops = [
            "wheat", "rice", "paddy", "maize", "cotton", "sugarcane",
            "tobacco", "barley", "millets", "oil seeds", "oilseeds",
            "pulses", "ground nuts", "groundnuts"
        ]
        return crop.strip().lower() in valid_crops
    
    def _is_valid_english_soil(self, soil: str) -> bool:
        """Check if soil type is a valid English soil type"""
        valid_soils = ["sandy", "loamy", "black", "red", "clayey"]
        return soil.strip().lower() in valid_soils

    def _apply_defaults(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """
        Apply default values for missing optional parameters

        Defaults are based on typical agricultural conditions and provide
        reasonable fallback values when specific measurements are unavailable.

        Args:
            params: Parameter dictionary (may have None values)

        Returns:
            Complete parameter dictionary with defaults applied
        """
        DEFAULTS = {
            "temperature": 25.0,  # Moderate temperature
            "humidity": 60.0,  # Moderate humidity
            "moisture": 50.0,  # Moderate soil moisture
            "nitrogen": 40.0,  # Average soil nitrogen
            "phosphorous": 30.0,  # Average soil phosphorous
            "potassium": 30.0  # Average soil potassium
        }

        complete = params.copy()

        for key, default_value in DEFAULTS.items():
            if complete.get(key) is None:
                complete[key] = default_value
                logger.info(f"{self.name}: Applied default {key}={default_value}")

        return complete

    def health_check(self) -> Dict[str, Any]:
        """
        Check health of fertilizer agent and its dependencies

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
