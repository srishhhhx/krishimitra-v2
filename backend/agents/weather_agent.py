"""
Weather Agent

Provides real-time weather information for agricultural decision-making.
Extracts location from natural language, converts to coordinates, and fetches
weather data via MCP server.

Key Features:
- LLM-based location extraction (cities, states, regions)
- Hindi/Hinglish language support
- Indian cities geocoding database (loaded from JSON)
- Weather data caching (15-min TTL)
- Agricultural weather insights
"""
import json
import os
import re
from typing import Dict, Any, Optional

from agents.base import ToolAgent, track_latency
from schemas.agents import AgentState
from tools.weather_tool import get_weather_data
from core.logging import get_logger

logger = get_logger(__name__)


# ============================================================================
# Load Indian Cities Geocoding Database from JSON
# ============================================================================

def _load_indian_cities() -> Dict[str, Dict[str, Any]]:
    """
    Load Indian cities geocoding data from JSON file.
    Returns flat dictionary with all locations (cities, states, aliases) merged.
    """
    json_path = os.path.join(os.path.dirname(__file__), "..", "data", "indian_cities.json")
    
    try:
        with open(json_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        
        # Merge all categories into single flat dict
        cities = {}
        for category in ["cities", "states", "northeast", "hill_states", "aliases"]:
            if category in data:
                cities.update(data[category])
        
        logger.info(f"Loaded {len(cities)} locations from indian_cities.json")
        return cities
        
    except FileNotFoundError:
        logger.error(f"Cities JSON file not found: {json_path}")
        return {}
    except json.JSONDecodeError as e:
        logger.error(f"Failed to parse cities JSON: {e}")
        return {}

# Load cities at module load time (cached)
INDIAN_CITIES = _load_indian_cities()



class WeatherAgent(ToolAgent):
    """
    Agent for weather information retrieval.

    This agent:
    1. Extracts location from natural language query (LLM-based)
    2. Converts location name to lat/lon coordinates (geocoding)
    3. Fetches weather data via MCP weather server
    4. Formats results with agricultural insights
    5. Supports Hindi/Hinglish queries

    Supports queries like:
    - "Weather in Bangalore"
    - "मौसम दिल्ली में"
    - "What's the temperature in Punjab?"
    - "Will it rain tomorrow in Karnataka?"
    """

    def __init__(self, generation_service):
        """
        Initialize Weather Agent

        Args:
            generation_service: Service for LLM generation (for location extraction)
        """
        super().__init__(
            name="weather_agent",
            description="Provides real-time weather information for agricultural planning",
            tool_callable=get_weather_data
        )
        self.generation_service = generation_service

    @track_latency("weather_agent")
    async def run(self, state: AgentState) -> AgentState:
        """
        Execute weather retrieval workflow (Orchestrator V2 Pattern)

        Workflow:
        1. Extract location from user query using LLM
        2. Convert location to lat/lon coordinates (geocoding)
        3. Fetch weather data via MCP weather tool
        4. Format results with agricultural context
        5. Update state with collected_findings["weather_agent"]

        Args:
            state: Current agent state with user_query

        Returns:
            Updated state with collected_findings["weather_agent"] containing:
                - status: "success" | "error" | "needs_clarification"
                - data: Weather information (temperature, humidity, insights)
                - OR error: Error message
                - OR clarification: Clarification question
        """
        # Initialize collected_findings if needed
        if "collected_findings" not in state:
            state["collected_findings"] = {}

        try:
            query = state.get("user_query", "")
            if not query:
                state["collected_findings"]["weather_agent"] = {
                    "status": "error",
                    "error": "No query provided"
                }
                return state

            logger.info(f"{self.name}: Processing query: {query[:100]}...")

            # Phase 0: Check for supervisor-extracted location FIRST (LLM consolidation)
            supervisor_location = state.get("user_context", {}).get("location")
            if supervisor_location:
                logger.info(f"{self.name}: Using supervisor-extracted location: {supervisor_location}")
                location_info = {"location": supervisor_location}
            else:
                # Phase 0.5: Resolve contextual references (BUG FIX #3)
                resolved_query, resolved_location = self._resolve_location_references(query, state)
                if resolved_location:
                    logger.info(f"{self.name}: Resolved contextual reference → {resolved_location}")
                    # Skip LLM extraction - use resolved location directly
                    location_info = {"location": resolved_location}
                else:
                    # Phase 1: Extract location from query using LLM (fallback only)
                    logger.info(f"{self.name}: No supervisor location, using LLM extraction")
                    location_info = await self._extract_location_with_llm(resolved_query)
                    logger.info(f"{self.name}: LLM extracted location: {location_info}")

            if not location_info or not location_info.get("location"):
                # No location found - ask for clarification
                state["collected_findings"]["weather_agent"] = {
                    "status": "needs_clarification",
                    "error": "Location not specified",
                    "clarification_question": "Which location would you like weather information for? (e.g., Bangalore, Delhi, Punjab)"
                }
                logger.warning(f"{self.name}: No location found in query")
                return state

            # Phase 2: Convert location to coordinates (geocoding)
            location_name = location_info["location"]
            coordinates = self._geocode_location(location_name)

            if not coordinates:
                state["collected_findings"]["weather_agent"] = {
                    "status": "needs_clarification",
                    "error": f"Location '{location_name}' not recognized",
                    "clarification_question": f"I don't recognize '{location_name}'. Please specify a major Indian city or state.",
                    "extracted_location": location_name
                }
                logger.warning(f"{self.name}: Failed to geocode location: {location_name}")
                return state

            lat, lon = coordinates["lat"], coordinates["lon"]
            resolved_location = coordinates.get("state", location_name)

            logger.info(f"{self.name}: Geocoded {location_name} → {lat:.4f}, {lon:.4f}")

            # Phase 3: Fetch weather data
            logger.info(f"{self.name}: Fetching weather data for {lat:.4f}, {lon:.4f}")

            weather_result = await self.tool_callable.ainvoke({
                "latitude": lat,
                "longitude": lon,
                "use_cache": True
            })

            # Phase 4: Check for errors
            if "error" in weather_result and weather_result["error"]:
                logger.error(f"{self.name}: Weather tool error: {weather_result['error']}")
                state["collected_findings"]["weather_agent"] = {
                    "status": "error",
                    "error": weather_result["error"],
                    "location": resolved_location,
                    "coordinates": {"lat": lat, "lon": lon}
                }
                return state

            # Phase 5: Enrich with agricultural insights
            weather_result["location"] = resolved_location
            weather_result["location_queried"] = location_name
            weather_result["agricultural_insights"] = self._generate_agricultural_insights(weather_result)

            # Phase 6: Update state with V2 pattern
            state["collected_findings"]["weather_agent"] = {
                "status": "success",
                "data": weather_result
            }

            logger.info(
                f"{self.name}: Weather for {resolved_location}: "
                f"{weather_result.get('temperature')}°C, {weather_result.get('humidity')}% humidity"
            )

            # Phase 7: Track agent execution
            if "executed_agents" not in state:
                state["executed_agents"] = []
            state["executed_agents"].append(self.name)

            return state

        except Exception as e:
            logger.error(f"{self.name} failed: {e}", exc_info=True)
            state["collected_findings"]["weather_agent"] = {
                "status": "error",
                "error": str(e)
            }
            return state

    async def _extract_location_with_llm(self, query: str) -> Dict[str, Optional[str]]:
        """
        Extract location from natural language query using LLM

        Supports:
        - City names: "Weather in Bangalore", "मौसम बैंगलोर में"
        - State names: "Punjab weather", "कर्नाटक का मौसम"
        - Implicit locations: "my city", "here"

        Args:
            query: User's natural language query

        Returns:
            Dict with extracted location (None if not found)
        """
        prompt = f"""Extract the location from this weather query:

User Query: "{query}"

Return ONLY a JSON object with the location:
{{
  "location": "<city or state name or null>"
}}

Examples:
Query: "Weather in Bangalore"
Response: {{"location": "Bangalore"}}

Query: "मौसम दिल्ली में"
Response: {{"location": "Delhi"}}

Query: "What's the temperature in Punjab?"
Response: {{"location": "Punjab"}}

Query: "Will it rain tomorrow?"
Response: {{"location": null}}

Query: "Current weather in Karnataka"
Response: {{"location": "Karnataka"}}

Only extract explicitly mentioned locations. Return null if no location is mentioned.
"""

        try:
            # Call LLM (using generate_answer which returns tuple)
            response, _ = self.generation_service.generate_answer(
                query=prompt,
                retrieved_chunks=[],
                max_tokens=100
            )

            # Extract JSON from response
            json_match = re.search(r'\{[^{}]*\}', response, re.DOTALL)
            if not json_match:
                logger.warning(f"{self.name}: No JSON found in LLM response")
                return {"location": None}

            result = json.loads(json_match.group())
            return result

        except json.JSONDecodeError as e:
            logger.error(f"{self.name}: Failed to parse LLM JSON: {e}")
            return {"location": None}
        except Exception as e:
            logger.error(f"{self.name}: LLM extraction failed: {e}")
            return {"location": None}

    def _geocode_location(self, location_name: str) -> Optional[Dict[str, Any]]:
        """
        Convert location name to lat/lon coordinates

        Uses Indian cities database for geocoding.

        Args:
            location_name: City or state name

        Returns:
            Dict with lat, lon, state (None if not found)
        """
        if not location_name:
            return None

        # Normalize location name (lowercase, strip)
        normalized = location_name.lower().strip()

        # Direct lookup
        if normalized in INDIAN_CITIES:
            return INDIAN_CITIES[normalized]

        # Try partial match (fuzzy)
        for city_key, coords in INDIAN_CITIES.items():
            if normalized in city_key or city_key in normalized:
                logger.info(f"{self.name}: Fuzzy matched '{location_name}' → '{city_key}'")
                return coords

        logger.warning(f"{self.name}: No geocoding match for '{location_name}'")
        return None

    def _generate_agricultural_insights(self, weather_data: Dict[str, Any]) -> str:
        """
        Generate agriculture-specific insights from weather data

        Args:
            weather_data: Weather data dictionary

        Returns:
            Agricultural insights string
        """
        temp = weather_data.get("temperature", 0)
        humidity = weather_data.get("humidity", 0)
        description = weather_data.get("description", "").lower()

        insights = []

        # Temperature insights
        if temp < 15:
            insights.append("⚠️ Low temperature - protect sensitive crops from cold stress")
        elif temp > 35:
            insights.append("⚠️ High temperature - ensure adequate irrigation")
        else:
            insights.append("✅ Temperature suitable for most crop activities")

        # Humidity insights
        if humidity > 80:
            insights.append("⚠️ High humidity - monitor for fungal diseases")
        elif humidity < 40:
            insights.append("⚠️ Low humidity - increase irrigation frequency")
        else:
            insights.append("✅ Humidity levels favorable for farming")

        # Weather condition insights
        if "rain" in description or "drizzle" in description:
            insights.append("🌧️ Rainfall expected - delay spraying activities")
        elif "clear" in description or "sunny" in description:
            insights.append("☀️ Clear weather - good for field operations")
        elif "cloud" in description:
            insights.append("☁️ Cloudy conditions - suitable for transplanting")

        return " | ".join(insights)

    def _resolve_location_references(
        self,
        query: str,
        state: AgentState
    ) -> tuple[str, Optional[str]]:
        """
        Resolve contextual location references (BUG FIX #3)

        Handles references like:
        - "there" → previous location mentioned
        - "that place" → previous location
        - "my city" → user's location from context
        - "same place" → previous location

        Resolution sources (in order):
        1. collected_findings from previous weather queries
        2. user_context["location"]
        3. conversation_history (extract location from previous queries)

        Args:
            query: User's query with potential references
            state: Current agent state with context

        Returns:
            Tuple of (resolved_query, resolved_location)
            - resolved_query: Query with references replaced
            - resolved_location: Extracted location or None
        """
        query_lower = query.lower()

        # Check if query contains contextual references
        contextual_references = [
            "there", "that place", "that city", "same place", "same location",
            "my city", "my location", "my place", "वहां", "वहाँ"  # Hindi: there
        ]

        has_reference = any(ref in query_lower for ref in contextual_references)

        if not has_reference:
            return query, None  # No reference to resolve

        logger.info(f"{self.name}: Detected contextual reference in query")

        # Resolution Strategy 1: Check collected_findings from previous agents
        if state.get("collected_findings"):
            # Check if weather_agent was previously executed
            if "weather_agent" in state["collected_findings"]:
                weather_finding = state["collected_findings"]["weather_agent"]
                if weather_finding.get("status") == "success":
                    data = weather_finding.get("data", {})
                    location = data.get("location") or data.get("location_queried")
                    if location:
                        logger.info(f"{self.name}: Resolved from previous weather query → {location}")
                        # Replace reference in query
                        for ref in contextual_references:
                            query = re.sub(rf'\b{ref}\b', location, query, flags=re.IGNORECASE)
                        return query, location

        # Resolution Strategy 2: Check user_context["location"]
        if state.get("user_context") and state["user_context"].get("location"):
            location = state["user_context"]["location"]
            logger.info(f"{self.name}: Resolved from user_context → {location}")
            for ref in contextual_references:
                query = re.sub(rf'\b{ref}\b', location, query, flags=re.IGNORECASE)
            return query, location

        # Resolution Strategy 3: Extract from conversation_history
        if state.get("conversation_history"):
            # Look for location mentions in previous queries (last 5 turns)
            for turn in reversed(state["conversation_history"][-5:]):
                user_query = turn.get("user_query", "")
                if not user_query:
                    continue

                # Try to extract location from previous query
                for city_name in INDIAN_CITIES.keys():
                    if city_name in user_query.lower():
                        logger.info(f"{self.name}: Resolved from conversation history → {city_name}")
                        for ref in contextual_references:
                            query = re.sub(rf'\b{ref}\b', city_name, query, flags=re.IGNORECASE)
                        return query, city_name

        # Could not resolve reference
        logger.warning(f"{self.name}: Could not resolve contextual reference")
        return query, None

    def health_check(self) -> Dict[str, Any]:
        """
        Check health of weather agent and dependencies

        Returns:
            Health status dictionary
        """
        status = super().health_check()

        # Check generation service
        status["generation_service_available"] = self.generation_service is not None

        # Check weather tool configured
        status["tool_configured"] = self.tool_callable is not None

        # Check geocoding database loaded
        status["geocoding_database_size"] = len(INDIAN_CITIES)

        # Overall health
        if not status["generation_service_available"]:
            status["status"] = "degraded"
        elif not status["tool_configured"]:
            status["status"] = "degraded"

        return status
