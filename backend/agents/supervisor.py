"""
Supervisor Agent for Multi-Agent Orchestration

The Supervisor is the "Brain" of the system that:
1. Classifies queries and creates agent plans
2. Routes to appropriate agents
3. Combines multi-agent clarification requests
4. Detects and handles interruptions
5. Prevents "I don't know" loops
6. Synthesizes final responses

KEY PRINCIPLE: Supervisor is the ONLY entity that talks to users.
Agents NEVER talk to users - they only declare missing info via clarification_state.
"""

import json
import re
from typing import Dict, Any, List, Optional, Tuple
from datetime import datetime

from schemas.supervisor import SupervisorState, ClarificationRequest, ConversationTurn
from schemas.agents import AgentState
from services.generation import generation_service
from core.logging import get_logger
from core.workflow_logging import workflow_log

logger = get_logger(__name__)


class SupervisorAgent:
    """
    Supervisor Agent - The Brain of Multi-Agent System

    Responsibilities:
    - Plan decomposition (query → list of agents)
    - Decision logic (which agent runs next)
    - Multi-agent clarification combining
    - Interruption detection and handling
    - Loop prevention ("I don't know" × 3 = fail gracefully)
    - Final response synthesis

    Does NOT execute tools directly - delegates to specialized agents.
    """

    def __init__(self, generation_service=None):
        """
        Initialize Supervisor Agent

        Args:
            generation_service: Service for LLM generation (for classification)
        """
        self.name = "supervisor"
        self.generation_service = generation_service or generation_service

        # Greeting patterns (non-agent queries)
        self.greeting_patterns = [
            r"\b(hello|hi|hey|namaste|namaskar|namaskaram)\b",
            r"\b(good morning|good afternoon|good evening)\b",
            r"\b(kaise ho|kya haal hai)\b",
        ]

        # Thank you patterns
        self.thanks_patterns = [
            r"\b(thank you|thanks|धन्यवाद|shukriya)\b",
            r"\b(appreciate|grateful)\b",
        ]

        # "I don't know" patterns for loop detection
        self.idk_patterns = [
            r"\b(i don't know|i do not know|idk|not sure|no idea)\b",
            r"\b(मुझे नहीं पता|पता नहीं)\b",
            r"\b(dunno|don't remember)\b",
        ]

        logger.info("SupervisorAgent initialized")

    async def run(self, state: SupervisorState) -> SupervisorState:
        """
        Execute Supervisor workflow

        Workflow:
        1. Check if first turn OR interruption → classify and plan
        2. Check for clarification needs → combine and return to user
        3. Execute next agent in plan
        4. If plan complete → synthesize and return final response

        Args:
            state: SupervisorState with user_query, clarification_state, agent_plan

        Returns:
            Updated SupervisorState with next_agent or final_response
        """
        try:
            query = state.get("user_query", "").strip()

            # DEBUG: Log state at start
            logger.info(f"[DEBUG] Supervisor.run() called - plan={state.get('agent_plan', [])}, executed={state.get('executed_agents', [])}")

            # Handle empty queries
            if not query:
                state["final_response"] = "I'm here to help! Please ask me a question about agriculture."
                state["is_active"] = False
                return state

            # Check if this is first turn or interruption
            if self._is_new_query(state):
                logger.info(f"New query detected: {query[:100]}")
                return await self._handle_new_query(state)

            # Check if user is responding to clarification
            if self._has_pending_clarification(state):
                logger.info("Processing clarification response")
                return await self._handle_clarification_response(state)

            # Check if any agent needs clarification
            if self._needs_clarification(state):
                logger.info("Agents need clarification")
                return self._prepare_clarification_for_user(state)

            # Check if plan is complete
            if self._is_plan_complete(state):
                logger.info("Agent plan complete, synthesizing response")
                return self._synthesize_final_response(state)

            # Route to next agent
            next_agent = self._get_next_agent(state)
            if next_agent:
                logger.info(f"Routing to next agent: {next_agent}")
                state["next_agent"] = next_agent
                return state

            # Fallback: no agent to route to
            logger.warning("No next agent found, plan may be empty")
            return self._synthesize_final_response(state)

        except Exception as e:
            logger.error(f"Supervisor failed: {e}", exc_info=True)
            state["final_response"] = (
                "I encountered an issue processing your request. "
                "Please try again or rephrase your question."
            )
            state["is_active"] = False
            return state

    # ========================================================================
    # Query Classification and Planning
    # ========================================================================

    async def _handle_new_query(self, state: SupervisorState) -> SupervisorState:
        """
        Handle new query: classify and create agent plan

        Steps:
        1. Check for non-agent queries (greetings, thanks)
        2. Classify query intent
        3. Create agent plan
        4. Reset ephemeral state

        Args:
            state: SupervisorState with user_query

        Returns:
            Updated state with agent_plan and next_agent
        """
        query = state["user_query"].lower()

        # Check for greetings
        if self._is_greeting(query):
            state["final_response"] = (
                "Hello! I'm Krishi Mitra, your agricultural advisor. "
                "I can help with crop recommendations, fertilizer advice, disease detection, "
                "weather information, and general farming knowledge. How can I assist you today?"
            )
            state["is_active"] = False
            return state

        # Check for thanks
        if self._is_thanks(query):
            state["final_response"] = (
                "You're welcome! Feel free to ask if you have more questions. "
                "Happy farming!"
            )
            state["is_active"] = False
            return state

        # =====================================================================
        # MULTI-TURN: Check for pending clarifications first
        # If an agent was waiting for info, route back to that agent
        # =====================================================================
        pending_agent = self._get_pending_clarification_agent(state)
        if pending_agent:
            logger.info(f"MULTI-TURN: Resuming clarification for {pending_agent}")
            
            # Get what fields were requested
            collected_findings = state.get("collected_findings", {})
            pending_finding = collected_findings.get(pending_agent, {})
            requested_fields = pending_finding.get("requested_fields", [])
            
            # Direct extraction for simple clarification responses
            query_lower = query.lower().strip()
            if "user_context" not in state:
                state["user_context"] = {}
            
            # Direct crop extraction
            crops = ["wheat", "rice", "maize", "cotton", "sugarcane", "groundnut", "soybean", "pulses", "vegetables", "coffee", "tea"]
            for crop in crops:
                if crop in query_lower:
                    state["user_context"]["crop_type"] = crop
                    logger.info(f"CLARIFICATION ENTITY (direct): crop_type={crop}")
                    break
            
            # Direct soil type extraction
            soils = ["sandy", "loamy", "clay", "clayey", "black", "red", "alluvial"]
            for soil in soils:
                if soil in query_lower:
                    state["user_context"]["soil_type"] = soil
                    logger.info(f"CLARIFICATION ENTITY (direct): soil_type={soil}")
                    break
            
            # Also try LLM extraction for complex responses
            agent_plan, extracted_entities = await self._classify_and_plan(state, is_clarification_response=True)
            for key, value in extracted_entities.items():
                if value is not None and state["user_context"].get(key) is None:
                    state["user_context"][key] = value
                    logger.info(f"CLARIFICATION ENTITY (llm): {key}={value}")
            
            # Route to the agent that was waiting for clarification
            state["agent_plan"] = []
            state["collected_findings"] = {}  # Clear old findings
            state["next_agent"] = pending_agent
            state["clarification_state"] = {}  # Clear pending clarification
            
            logger.info(f"MULTI-TURN: Routing to {pending_agent} with context: {state['user_context']}")
            return state

        # Normal classification flow
        agent_plan, extracted_entities = await self._classify_and_plan(state)

        # Store extracted entities in user_context (filter out None values)
        if "user_context" not in state:
            state["user_context"] = {}
        
        for key, value in extracted_entities.items():
            if value is not None:
                state["user_context"][key] = value
                logger.info(f"ENTITY STORED: {key}={value} -> user_context")

        # Reset ephemeral fields for new query (but keep user_context!)
        state["agent_plan"] = agent_plan
        state["clarification_state"] = {}
        state["collected_findings"] = {}
        state["next_agent"] = None
        state["final_response"] = ""

        # Append to conversation history
        state["conversation_history"].append({
            "role": "user",
            "content": state["user_query"],  # Use original query with case preserved
            "timestamp": datetime.utcnow().isoformat()
        })

        # Set next agent and pop from plan (CRITICAL FIX: prevent infinite loop)
        if agent_plan:
            state["next_agent"] = agent_plan.pop(0)  # Pop first agent from plan
            state["agent_plan"] = agent_plan  # Save modified plan

        logger.info(f"Agent plan created: {agent_plan}, next_agent: {state.get('next_agent')}")

        return state

    def _get_pending_clarification_agent(self, state: SupervisorState) -> Optional[str]:
        """
        Check if any agent has a pending clarification request from previous turn.
        
        This enables multi-turn conversations where:
        - Turn 1: "What fertilizer?" -> fertilizer_agent asks for crop/soil
        - Turn 2: "I am growing wheat" -> should route back to fertilizer_agent
        
        Returns:
            Agent name if there's a pending clarification, None otherwise
        """
        collected_findings = state.get("collected_findings", {})
        logger.info(f"[DEBUG] Checking pending clarifications. collected_findings keys: {list(collected_findings.keys())}")
        
        for agent_name, finding in collected_findings.items():
            if isinstance(finding, dict) and finding.get("status") == "needs_clarification":
                logger.info(f"Found pending clarification for {agent_name}: {finding.get('requested_fields', [])}")
                return agent_name
        
        return None

    async def _classify_and_plan(self, state_or_query, is_clarification_response: bool = False) -> tuple[List[str], Dict[str, Any]]:
        """
        Classify query AND extract entities in a single LLM call.
        Now supports multi-turn context by accepting state with conversation history.

        Args:
            state_or_query: Either SupervisorState dict or query string (backward compat)
            is_clarification_response: True if this is a response to a clarification request

        Returns:
            Tuple of (agent_plan, extracted_entities)
        """
        # Handle both state dict and raw query string
        if isinstance(state_or_query, dict):
            query = state_or_query.get("user_query", "")
            conversation_history = state_or_query.get("conversation_history", [])
            user_context = state_or_query.get("user_context", {})
            collected_findings = state_or_query.get("collected_findings", {})
        else:
            query = state_or_query
            conversation_history = []
            user_context = {}
            collected_findings = {}

        # Initialize default entities
        extracted_entities = {
            "location": None,
            "soil_type": None,
            "crop_type": None,
            "n_value": None,
            "p_value": None,
            "k_value": None,
            "temperature": None,
            "humidity": None,
            "ph": None,
            "rainfall": None,
        }

        # =====================================================================
        # Build conversation context for multi-turn awareness
        # =====================================================================
        context_str = ""
        
        # Add previous turns (last 3 for context window efficiency)
        if conversation_history and len(conversation_history) > 0:
            recent_turns = conversation_history[-3:]  # Last 3 turns max
            context_parts = []
            for turn in recent_turns:
                role = turn.get("role", "user")
                content = turn.get("content", "")[:100]  # Truncate long content
                context_parts.append(f"{role}: {content}")
            context_str = "\n".join(context_parts)
        
        # Add pending clarification info
        pending_clarification = ""
        for agent_name, finding in collected_findings.items():
            if isinstance(finding, dict) and finding.get("status") == "needs_clarification":
                fields = finding.get("requested_fields", [])
                pending_clarification = f"PENDING: {agent_name} waiting for: {fields}"
                break

        # =====================================================================
        # NO PRE-CLASSIFICATION - LLM is the ONLY decision maker
        # =====================================================================
        has_image = hasattr(self, 'current_images') and self.current_images

        classification_prompt = f"""You are the brain of an agricultural assistant. Classify user queries.

CURRENT QUERY: "{query}"
HAS_IMAGE: {has_image}
{"CONVERSATION CONTEXT:" if context_str else ""}
{context_str}
{"" if not pending_clarification else pending_clarification}

AVAILABLE AGENTS:
1. weather_agent: Gets REAL-TIME weather for a location
   - PROVIDES: temperature, humidity, conditions
   - REQUIRES: location name

2. crop_agent: Recommends crops based on soil and climate
   - PROVIDES: recommended crop, alternatives, confidence
   - REQUIRES: N, P, K, temperature, humidity, pH, rainfall
   - CAN INFER: NPK from soil_type, climate from location

3. fertilizer_agent: Recommends fertilizers for specific crops
   - PROVIDES: fertilizer name, NPK ratio, application advice
   - REQUIRES: crop_type, soil_type

4. disease_detection_agent: Identifies plant diseases from IMAGES
   - PROVIDES: disease name, treatment, confidence
   - REQUIRES: plant image (ONLY use if HAS_IMAGE is true)

5. general_rag_agent: Answers farming questions from knowledge base
   - PROVIDES: informational answers about techniques, practices, pests, varieties
   - USE FOR: cultivation methods, pest information, crop varieties, disease symptoms (text-based)

REASONING STEPS:
1. What does the user want to know?
2. What information did they provide?
3. What information is MISSING but needed?
4. Which agents should run, and in what ORDER?

CRITICAL MULTI-AGENT RULES:
- For LOCATION-specific queries → ALWAYS get weather_agent first for climate context
- For "best practices" + location → weather_agent → crop_agent → general_rag_agent (3 agents)
- For pest/disease + location → weather_agent → general_rag_agent (pest activity varies with climate)
- For crop + fertilizer requests → weather_agent → crop_agent → fertilizer_agent (3 agents)
- For text-based disease/pest queries (no image) → general_rag_agent (or with location: weather + RAG)
- disease_detection_agent ONLY if HAS_IMAGE is true

EXAMPLES:

Example 1: Regional cultivation (3 agents)
Query: "Best practices for growing rice in Kerala?"
{{
  "user_intent": "Kerala-specific rice cultivation advice",
  "info_provided": ["location: Kerala", "crop: rice"],
  "info_missing": ["current climate", "soil conditions"],
  "agents": ["weather_agent", "crop_agent", "general_rag_agent"],
  "reasoning": "User wants Kerala-specific advice. Need weather for monsoon context, verify rice suitability, then get region-specific practices.",
  "entities": {{"location": "Kerala", "soil_type": null, "crop_type": "rice", "n_value": null, "p_value": null, "k_value": null}}
}}

Example 2: Pest with location context (2 agents)
Query: "I'm growing cotton in Maharashtra, seeing pest damage. Help?"
{{
  "user_intent": "cotton pest identification and treatment",
  "info_provided": ["location: Maharashtra", "crop: cotton", "symptom: pest damage"],
  "info_missing": ["current climate affects pest activity"],
  "agents": ["weather_agent", "general_rag_agent"],
  "reasoning": "Pest identification depends on climate. Get Maharashtra weather (pest activity varies with temperature/humidity), then search for cotton pests.",
  "entities": {{"location": "Maharashtra", "soil_type": null, "crop_type": "cotton", "n_value": null, "p_value": null, "k_value": null}}
}}

Example 3: Location-based crop (2 agents)
Query: "What crop should I grow in Pune?"
{{
  "user_intent": "crop recommendation for Pune",
  "info_provided": ["location: Pune"],
  "info_missing": ["temperature", "humidity", "soil"],
  "agents": ["weather_agent", "crop_agent"],
  "reasoning": "Need Pune climate first, then recommend suitable crops.",
  "entities": {{"location": "Pune", "soil_type": null, "crop_type": null, "n_value": null, "p_value": null, "k_value": null}}
}}

Example 4: Crop + fertilizer for location (3 agents)
Query: "What crop and fertilizer for Tamil Nadu?"
{{
  "user_intent": "crop AND fertilizer for Tamil Nadu",
  "info_provided": ["location: Tamil Nadu"],
  "info_missing": ["climate", "soil"],
  "agents": ["weather_agent", "crop_agent", "fertilizer_agent"],
  "reasoning": "Multi-intent: Get weather, recommend crop, then recommend fertilizer for that crop.",
  "entities": {{"location": "Tamil Nadu", "soil_type": null, "crop_type": null, "n_value": null, "p_value": null, "k_value": null}}
}}

Example 5: Disease symptoms text (1-2 agents)
Query: "My tomato leaves have yellow spots"
{{
  "user_intent": "diagnose tomato leaf problem",
  "info_provided": ["crop: tomato", "symptom: yellow spots"],
  "info_missing": ["location for climate context"],
  "agents": ["general_rag_agent"],
  "reasoning": "Text-based symptom description, no image provided. Search knowledge base for tomato leaf diseases.",
  "entities": {{"location": null, "soil_type": null, "crop_type": "tomato", "n_value": null, "p_value": null, "k_value": null}}
}}

Example 6: Simple knowledge query (1 agent)
Query: "What is SRI method?"
{{
  "user_intent": "learn about SRI technique",
  "info_provided": [],
  "info_missing": [],
  "agents": ["general_rag_agent"],
  "reasoning": "Pure knowledge query about agricultural technique. No location/crop context needed.",
  "entities": {{"location": null, "soil_type": null, "crop_type": null, "n_value": null, "p_value": null, "k_value": null}}
}}

Example 7: Fertilizer with crop+soil (1 agent)
Query: "What fertilizer for wheat on black soil?"
{{
  "user_intent": "fertilizer for wheat",
  "info_provided": ["crop: wheat", "soil: black"],
  "info_missing": [],
  "agents": ["fertilizer_agent"],
  "reasoning": "User provided crop and soil. Can recommend fertilizer directly.",
  "entities": {{"location": null, "soil_type": "black", "crop_type": "wheat", "n_value": null, "p_value": null, "k_value": null}}
}}

Example 8: Rice variety query (1 agent)
Query: "Recommend rice variety for black soil"
{{
  "user_intent": "rice variety recommendation",
  "info_provided": ["crop: rice", "soil: black"],
  "info_missing": [],
  "agents": ["general_rag_agent"],
  "reasoning": "Variety information comes from knowledge base, not ML model.",
  "entities": {{"location": null, "soil_type": "black", "crop_type": "rice", "n_value": null, "p_value": null, "k_value": null}}
}}

Example 9: Direct NPK parameters (1 agent)
Query: "What crop for N=80 P=40 K=40 temp=25?"
{{
  "user_intent": "crop with specific parameters",
  "info_provided": ["N: 80", "P: 40", "K: 40", "temp: 25"],
  "info_missing": ["humidity", "rainfall", "pH - will use defaults"],
  "agents": ["crop_agent"],
  "reasoning": "User provided NPK and temp directly. Go straight to ML prediction.",
  "entities": {{"location": null, "soil_type": null, "crop_type": null, "n_value": 80, "p_value": 40, "k_value": 40}}
}}

Return ONLY valid JSON:
{{
  "user_intent": "brief intent description",
  "info_provided": ["list of info"],
  "info_missing": ["what's needed"],
  "agents": ["agent1", "agent2"],
  "reasoning": "why this order",
  "entities": {{
    "location": "location or null",
    "soil_type": "soil or null",
    "crop_type": "crop or null",
    "n_value": null,
    "p_value": null,
    "k_value": null
  }}
}}
"""

        try:
            # Call LLM for reasoning-based classification (Phase 1 Enhancement)
            response, _ = self.generation_service.generate_answer(
                query=classification_prompt,
                retrieved_chunks=[],
                max_tokens=600,  # Increased for reasoning + entities
                temperature=0.0
            )

            # DEBUG: Log raw LLM response
            logger.info(f"[DEBUG] Raw LLM classification response: {response[:500]}")

            # Strip markdown code blocks if present (Gemini sometimes wraps JSON in ```)
            response_clean = response.strip()
            if response_clean.startswith("```json"):
                response_clean = response_clean[7:]  # Remove ```json
            if response_clean.startswith("```"):
                response_clean = response_clean[3:]  # Remove ```
            if response_clean.endswith("```"):
                response_clean = response_clean[:-3]  # Remove trailing ```
            response_clean = response_clean.strip()

            # Parse JSON response
            classification = json.loads(response_clean)
            agent_plan = classification.get("agents", [])
            reasoning = classification.get("reasoning", "")
            entities = classification.get("entities", {})

            # DEBUG: Log parsed classification
            logger.info(f"[DEBUG] Parsed classification: agents={agent_plan}, entities={entities}")

            # Merge extracted entities (only non-null values)
            for key, value in entities.items():
                if value is not None and key in extracted_entities:
                    extracted_entities[key] = value

            # Validate agent names
            valid_agents = [
                "disease_detection_agent",
                "fertilizer_agent",
                "crop_agent",
                "weather_agent",
                "general_rag_agent"
            ]

            agent_plan = [agent for agent in agent_plan if agent in valid_agents]

            # Fallback to general RAG if no valid agents
            if not agent_plan:
                logger.warning(f"No valid agents in plan, defaulting to general_rag_agent. Response: {response}")
                agent_plan = ["general_rag_agent"]


            # ================================================================
            # HYBRID VALIDATION LAYER (Post-LLM)
            # Validates LLM decisions, adds missing agents, logs warnings
            # Does NOT override LLM - only enhances and warns
            # ================================================================
            validation_warnings = []
            location = extracted_entities.get("location")
            crop_type = extracted_entities.get("crop_type")
            
            # Validation 1: Location mentioned but weather_agent missing
            if location and "crop_agent" in agent_plan and "weather_agent" not in agent_plan:
                validation_warnings.append(f"Location '{location}' provided but weather_agent not in plan")
                agent_plan.insert(0, "weather_agent")
                reasoning = reasoning + " [Validation: Added weather_agent for climate context]"
                logger.info(f"VALIDATION: Added weather_agent before crop_agent for location '{location}'")
            
            # Validation 2: Pest/disease query with location should include weather
            query_lower = query.lower()
            pest_keywords = ['pest', 'disease', 'insect', 'damage', 'infection', 'blight', 'wilt']
            is_pest_query = any(kw in query_lower for kw in pest_keywords)
            if is_pest_query and location and "weather_agent" not in agent_plan:
                validation_warnings.append(f"Pest/disease query with location but no weather context")
                if "general_rag_agent" in agent_plan:
                    agent_plan.insert(0, "weather_agent")
                    reasoning = reasoning + " [Validation: Added weather_agent - pest activity varies with climate]"
                    logger.info(f"VALIDATION: Added weather_agent for pest query with location")
            
            # Validation 3: Fertilizer without crop context
            if "fertilizer_agent" in agent_plan and "crop_agent" not in agent_plan:
                if not crop_type and location:
                    validation_warnings.append("Fertilizer requested without crop - may need crop recommendation first")
                    logger.info("VALIDATION WARNING: Fertilizer without crop type. Consider adding crop_agent.")
            
            # Validation 4: Best practices query should include RAG
            if "best practice" in query_lower or "how to grow" in query_lower:
                if "general_rag_agent" not in agent_plan:
                    agent_plan.append("general_rag_agent")
                    reasoning = reasoning + " [Validation: Added RAG for cultivation practices]"
                    logger.info("VALIDATION: Added general_rag_agent for best practices query")
            
            # Log validation warnings
            if validation_warnings:
                logger.info(f"VALIDATION WARNINGS: {validation_warnings}")

            # Log classification with enhanced formatting
            workflow_log.log_classification(
                intent="multi_agent" if len(agent_plan) > 1 else (agent_plan[0] if agent_plan else "unknown"),
                agents=agent_plan,
                reasoning=reasoning
            )

            # ================================================================
            # REASONING TRACE LOGGING (Clean format, no emojis)
            # ================================================================
            user_intent = classification.get("user_intent", "")
            info_provided = classification.get("info_provided", [])
            info_missing = classification.get("info_missing", [])
            
            logger.info("=" * 80)
            logger.info("SUPERVISOR REASONING TRACE")
            logger.info("=" * 80)
            logger.info(f"Query: {query}")
            logger.info(f"INTENT: {user_intent}")
            logger.info(f"PROVIDED: {info_provided}")
            logger.info(f"MISSING: {info_missing}")
            logger.info(f"AGENT PLAN: {' -> '.join(agent_plan)}")
            logger.info(f"REASONING: {reasoning}")
            if validation_warnings:
                logger.info(f"VALIDATIONS APPLIED: {len(validation_warnings)}")
            logger.info("=" * 80)
            
            # Log ReAct-style thought for visualization
            if user_intent:
                thought_msg = f"User wants: {user_intent}. "
                if info_provided:
                    thought_msg += f"Provided: {', '.join(info_provided[:3])}. "
                if info_missing:
                    thought_msg += f"Need: {', '.join(info_missing[:3])}."
                workflow_log.log_thought(thought_msg, step=1)
            
            # Log the action plan
            if len(agent_plan) > 1:
                workflow_log.log_thought(
                    f"This requires a multi-agent chain: {' -> '.join(agent_plan)}. "
                    f"Each agent will pass data to the next.",
                    step=2
                )

            # Log extracted entities
            non_null_entities = {k: v for k, v in extracted_entities.items() if v is not None}
            if non_null_entities:
                logger.info(f"ENTITIES EXTRACTED: {non_null_entities}")

            return agent_plan, extracted_entities

        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse classification JSON: {e}. Response: {response}")
            # Fallback to pattern-based routing
            return self._pattern_based_fallback(query, extracted_entities)

        except Exception as e:
            logger.error(f"Classification failed: {e}", exc_info=True)
            # Fallback to pattern-based routing
            return self._pattern_based_fallback(query, extracted_entities)
    
    def _pattern_based_fallback(self, query: str, extracted_entities: Dict[str, Any]) -> Tuple[List[str], Dict[str, Any]]:
        """
        Pattern-based fallback routing when LLM classification fails.
        Used only as a safety net - not the primary routing mechanism.
        
        Returns:
            Tuple of (agent_plan, extracted_entities)
        """
        logger.info("FALLBACK: Using pattern-based routing due to LLM failure")
        query_lower = query.lower()
        agent_plan = []
        
        # Pattern 1: Location detection -> add weather
        location_patterns = [
            r'\b(in|for|at)\s+([A-Z][a-z]+(?:\s+[A-Z][a-z]+)?)',  # "in Pune", "for Tamil Nadu"
            r'\b(punjab|maharashtra|karnataka|kerala|tamil\s*nadu|andhra|telangana|gujarat|rajasthan)\b'
        ]
        location_match = None
        for pattern in location_patterns:
            match = re.search(pattern, query, re.IGNORECASE)
            if match:
                location_match = match.group(0)
                extracted_entities["location"] = location_match
                break
        
        # Pattern 2: Crop keywords
        crop_keywords = ['crop', 'grow', 'plant', 'cultivate', 'farming', 'yield']
        is_crop_query = any(kw in query_lower for kw in crop_keywords)
        
        # Pattern 3: Fertilizer keywords
        fertilizer_keywords = ['fertilizer', 'fertiliser', 'npk', 'urea', 'nutrient']
        is_fertilizer_query = any(kw in query_lower for kw in fertilizer_keywords)
        
        # Pattern 4: Disease/pest keywords
        pest_keywords = ['disease', 'pest', 'infection', 'yellow', 'spot', 'wilt', 'blight']
        is_pest_query = any(kw in query_lower for kw in pest_keywords)
        
        # Pattern 5: Weather keywords
        weather_keywords = ['weather', 'temperature', 'humidity', 'rain', 'climate']
        is_weather_query = any(kw in query_lower for kw in weather_keywords)
        
        # Build agent plan based on patterns
        if is_weather_query:
            agent_plan.append("weather_agent")
        elif is_crop_query:
            if location_match:
                agent_plan.append("weather_agent")
            agent_plan.append("crop_agent")
        elif is_fertilizer_query:
            agent_plan.append("fertilizer_agent")
        elif is_pest_query:
            if location_match:
                agent_plan.append("weather_agent")
            agent_plan.append("general_rag_agent")
        else:
            # Default to RAG for general queries
            agent_plan.append("general_rag_agent")
        
        logger.info(f"FALLBACK RESULT: agents={agent_plan}, entities={extracted_entities}")
        return agent_plan, extracted_entities

    # ========================================================================
    # Clarification Handling
    # ========================================================================

    def _has_pending_clarification(self, state: SupervisorState) -> bool:
        """
        Check if there are pending clarification requests from previous turn

        Args:
            state: SupervisorState

        Returns:
            True if any agent has pending clarification
        """
        clarification_state = state.get("clarification_state", {})
        return any(req is not None for req in clarification_state.values())

    def _needs_clarification(self, state: SupervisorState) -> bool:
        """
        Check if any agent currently needs clarification

        Args:
            state: SupervisorState

        Returns:
            True if any agent set clarification_state
        """
        clarification_state = state.get("clarification_state", {})

        for agent_name, clarification_req in clarification_state.items():
            if clarification_req and clarification_req.get("needs_clarification"):
                return True

        return False

    def _prepare_clarification_for_user(self, state: SupervisorState) -> SupervisorState:
        """
        Combine clarification requests from multiple agents into ONE question

        Strategy: Ask for ALL missing fields at once with clear formatting

        Example:
            WeatherAgent needs: location
            CropAgent needs: soil_type

            Combined: "To continue, I need:
                      1. Your location (for weather information)
                      2. Your soil type (for crop recommendation)"

        Args:
            state: SupervisorState with clarification_state

        Returns:
            Updated state with final_response containing combined question
        """
        clarification_state = state.get("clarification_state", {})

        # Collect all clarification requests
        pending_clarifications = []
        for agent_name, clarification_req in clarification_state.items():
            if clarification_req and clarification_req.get("needs_clarification"):
                pending_clarifications.append((agent_name, clarification_req))

        if not pending_clarifications:
            return state

        # If only one agent needs clarification, use its question directly
        if len(pending_clarifications) == 1:
            agent_name, clarification_req = pending_clarifications[0]
            state["final_response"] = clarification_req["question_for_user"]
            state["is_active"] = True  # Waiting for user response
            return state

        # Multiple agents need clarification - combine
        combined_question = "To continue, I need:\n"

        field_counter = 1
        for agent_name, clarification_req in pending_clarifications:
            requested_fields = clarification_req.get("requested_fields", [])
            missing_descriptions = clarification_req.get("missing_field_descriptions", {})

            for field in requested_fields:
                description = missing_descriptions.get(field, f"Please provide {field}")
                combined_question += f"{field_counter}. {description}\n"
                field_counter += 1

        state["final_response"] = combined_question
        state["is_active"] = True  # Waiting for user response

        logger.info(f"Combined clarification from {len(pending_clarifications)} agents")

        return state

    async def _handle_clarification_response(self, state: SupervisorState) -> SupervisorState:
        """
        Process user's response to clarification request

        Steps:
        1. Extract information from user's response
        2. Update user_context with new information
        3. Check for "I don't know" loop
        4. Reset clarification_state
        5. Route back to waiting agent(s)

        Args:
            state: SupervisorState with user_query (user's answer)

        Returns:
            Updated state with user_context and cleared clarification_state
        """
        user_response = state["user_query"]
        clarification_state = state.get("clarification_state", {})

        # Check for "I don't know" pattern
        if self._is_idk_response(user_response):
            # Increment retry counts for all waiting agents
            max_reached = self._increment_retry_counts(state)

            if max_reached:
                # Max attempts reached - fail gracefully
                state["final_response"] = (
                    "I understand you're unsure about some details. "
                    "Let me help you differently. Could you describe your situation, "
                    "and I'll guide you on how to find this information?"
                )
                state["is_active"] = False
                state["clarification_state"] = {}
                return state
            else:
                # Ask again with more guidance
                state["final_response"] = self._rephrase_clarification_with_help(state)
                return state

        # Extract information from user response
        extracted_info = await self._extract_clarification_info(user_response, state)

        # Update user_context
        state["user_context"].update(extracted_info)

        # Clear clarification_state - agents will re-check fields
        state["clarification_state"] = {}

        # Keep agent_plan intact - resume execution
        # Supervisor will route to first agent in plan again

        logger.info(f"Clarification response processed: extracted {len(extracted_info)} fields")

        return state

    async def _extract_clarification_info(
        self,
        user_response: str,
        state: SupervisorState
    ) -> Dict[str, Any]:
        """
        Extract structured information from user's clarification response

        Uses LLM to parse natural language response into structured fields.

        Args:
            user_response: User's natural language answer
            state: SupervisorState with clarification_state (to know what we asked for)

        Returns:
            Dict of extracted field values

        Example:
            user_response = "sandy soil and wheat crop"
            → {"soil_type": "sandy", "crop_type": "wheat"}
        """
        clarification_state = state.get("clarification_state", {})

        # Build list of fields we're looking for
        all_requested_fields = []
        field_types = {}
        allowed_values = {}

        for agent_name, clarification_req in clarification_state.items():
            if clarification_req and clarification_req.get("needs_clarification"):
                requested_fields = clarification_req.get("requested_fields", [])
                all_requested_fields.extend(requested_fields)
                field_types.update(clarification_req.get("field_types", {}))
                allowed_values.update(clarification_req.get("allowed_values", {}))

        if not all_requested_fields:
            return {}

        # Build extraction prompt
        extraction_prompt = f"""
Extract agricultural parameters from this user response.

User's answer: "{user_response}"

Fields to extract:
"""
        for field in all_requested_fields:
            field_type = field_types.get(field, "string")
            prompt_part = f"- {field} ({field_type})"

            if field in allowed_values:
                prompt_part += f" - allowed values: {allowed_values[field]}"

            extraction_prompt += prompt_part + "\n"

        extraction_prompt += """
Return ONLY valid JSON with extracted values:
{{"field_name": "value", "field_name2": "value2"}}

If a field is not mentioned, set it to null.
Normalize values (e.g., "मक्का" → "maize", "काली मिट्टी" → "black").
"""

        try:
            # Call LLM for extraction (sync method, no await)
            response, _ = self.generation_service.generate_answer(
                query=extraction_prompt,
                retrieved_chunks=[],
                max_tokens=300,
                temperature=0.0
            )

            # Parse JSON response
            extracted_info = json.loads(response)

            # Remove null values
            extracted_info = {k: v for k, v in extracted_info.items() if v is not None}

            logger.info(f"Extracted from clarification: {extracted_info}")

            return extracted_info

        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse extraction JSON: {e}. Response: {response}")
            return {}

        except Exception as e:
            logger.error(f"Extraction failed: {e}", exc_info=True)
            return {}

    def _is_idk_response(self, response: str) -> bool:
        """Check if response matches 'I don't know' patterns"""
        response_lower = response.lower()
        return any(re.search(pattern, response_lower) for pattern in self.idk_patterns)

    def _increment_retry_counts(self, state: SupervisorState) -> bool:
        """
        Increment retry_count for all waiting agents

        Returns:
            True if any agent reached max_attempts, False otherwise
        """
        clarification_state = state.get("clarification_state", {})
        max_reached = False

        for agent_name, clarification_req in clarification_state.items():
            if clarification_req and clarification_req.get("needs_clarification"):
                retry_count = clarification_req.get("retry_count", 0)
                max_attempts = clarification_req.get("max_attempts", 3)

                clarification_req["retry_count"] = retry_count + 1

                if clarification_req["retry_count"] >= max_attempts:
                    max_reached = True
                    logger.warning(f"{agent_name} reached max retry attempts ({max_attempts})")

        return max_reached

    def _rephrase_clarification_with_help(self, state: SupervisorState) -> str:
        """
        Rephrase clarification question with more guidance

        Adds helpful context to help user answer the question.

        Args:
            state: SupervisorState with clarification_state

        Returns:
            Rephrased question with guidance
        """
        clarification_state = state.get("clarification_state", {})

        # Get first pending clarification
        for agent_name, clarification_req in clarification_state.items():
            if clarification_req and clarification_req.get("needs_clarification"):
                original_question = clarification_req["question_for_user"]
                requested_fields = clarification_req.get("requested_fields", [])

                # Add guidance based on field type
                guidance = "\n\nHere are some tips:\n"

                if "soil_type" in requested_fields:
                    guidance += "- Soil types: sandy, loamy, black, red, or clayey\n"

                if "crop_type" in requested_fields:
                    guidance += "- Common crops: wheat, rice, maize, cotton, sugarcane\n"

                if "location" in requested_fields:
                    guidance += "- Location can be city name, district, or state\n"

                return original_question + guidance

        return "Could you provide more details?"

    # ========================================================================
    # Routing and Execution Control
    # ========================================================================

    def _is_new_query(self, state: SupervisorState) -> bool:
        """
        Check if this is a new query (not a clarification response or continuation)

        Three scenarios trigger new query:
        1. First turn (no agent_plan AND no executed_agents)
        2. Interruption (user asks different question during clarification)
        3. New user message after previous conversation ended

        Args:
            state: SupervisorState

        Returns:
            True if new query should be classified
        """
        # CRITICAL FIX: Check executed_agents to prevent infinite loop
        # If agents have already executed in this turn, don't treat it as new query
        executed_agents = state.get("executed_agents", [])
        agent_plan = state.get("agent_plan", [])

        # First turn: no plan AND no executed agents
        if not agent_plan and len(executed_agents) == 0:
            return True

        # If plan is empty but agents were executed, it means plan completed
        # → NOT a new query, should synthesize response
        if not agent_plan and len(executed_agents) > 0:
            return False

        # Check for interruption: user asks new question during clarification
        if self._has_pending_clarification(state):
            # Detect if user's query is DIFFERENT from clarification context
            # Simple heuristic: if query mentions a different agent's domain
            query_lower = state["user_query"].lower()

            # Check if query indicates topic change
            topic_change_indicators = [
                "actually", "instead", "wait", "no", "forget", "never mind",
                "tell me about", "what about", "how about"
            ]

            if any(indicator in query_lower for indicator in topic_change_indicators):
                logger.info("Interruption detected: user changed topic during clarification")
                return True

        return False

    def _get_next_agent(self, state: SupervisorState) -> Optional[str]:
        """
        Get next agent to execute from plan

        Pops first agent from agent_plan.

        Args:
            state: SupervisorState with agent_plan

        Returns:
            Next agent name or None if plan empty
        """
        agent_plan = state.get("agent_plan", [])

        if not agent_plan:
            return None

        # Pop first agent
        next_agent = agent_plan.pop(0)
        state["agent_plan"] = agent_plan

        # ReAct ACTION logging
        remaining = len(agent_plan)
        reason = f"Executing step in plan. {remaining} agent(s) remaining after this."
        workflow_log.log_action(
            action="Execute",
            agent=next_agent,
            reason=reason
        )

        return next_agent

    def _is_plan_complete(self, state: SupervisorState) -> bool:
        """
        Check if agent execution plan is complete

        Args:
            state: SupervisorState

        Returns:
            True if no more agents to execute
        """
        agent_plan = state.get("agent_plan", [])
        return len(agent_plan) == 0 and not self._needs_clarification(state)

    # ========================================================================
    # Response Synthesis
    # ========================================================================

    def _synthesize_final_response(self, state: SupervisorState) -> SupervisorState:
        """
        Synthesize final response from collected agent findings

        Combines results from all executed agents into coherent response.
        Handles partial failures (some agents succeeded, some failed).

        Args:
            state: SupervisorState with collected_findings

        Returns:
            Updated state with final_response
        """
        collected_findings = state.get("collected_findings", {})

        # CRITICAL: Clear next_agent to prevent infinite loop
        state["next_agent"] = None

        if not collected_findings:
            # Graceful fallback for gibberish/off-topic queries
            state["final_response"] = (
                "I'm Krishi Mitra, your agricultural advisor. "
                "I can help with crop recommendations, fertilizer advice, disease detection, "
                "weather information, and general farming questions. "
                "Please ask me something about farming!"
            )
            state["is_active"] = False
            return state

        # Build response from findings
        response_parts = []

        # Process each agent's findings with type safety
        for agent_name, finding in collected_findings.items():
            # Type safety: skip None or non-dict findings
            if not isinstance(finding, dict):
                logger.warning(f"Skipping invalid finding for {agent_name}: {type(finding)}")
                continue
                
            status = finding.get("status")

            if status == "success":
                data = finding.get("data", {})
                formatted = self._format_agent_output(agent_name, data)
                if formatted:
                    response_parts.append(formatted)

            elif status == "error":
                error_msg = finding.get("error", "Unknown error")
                response_parts.append(f"⚠️ {agent_name}: {error_msg}")

            elif status == "needs_clarification":
                clarification_q = finding.get("clarification_question", "")
                missing_fields = finding.get("missing_fields", [])
                if clarification_q:
                    response_parts.append(f"❓ **Need More Information**\n\n{clarification_q}")
                elif missing_fields:
                    response_parts.append(f"❓ **Need More Information**\n\nPlease provide: {', '.join(missing_fields)}")

        # Combine all parts
        if response_parts:
            state["final_response"] = "\n\n".join(response_parts)
        else:
            state["final_response"] = (
                "I couldn't complete your request. Some services may be unavailable."
            )

        state["is_active"] = False

        # Append to conversation history
        state["conversation_history"].append({
            "role": "assistant",
            "content": state["final_response"],
            "timestamp": datetime.utcnow().isoformat()
        })

        logger.info(f"Final response synthesized: {len(state['final_response'])} chars")

        return state

    def _format_agent_output(self, agent_name: str, data: Dict[str, Any]) -> str:
        """
        Format agent output for user-facing display

        Different agents have different output formats.

        Args:
            agent_name: Name of agent
            data: Agent's output data

        Returns:
            Formatted string for display
        """
        if agent_name == "fertilizer_agent":
            fertilizer_name = data.get("fertilizer_name", "Unknown")
            npk_ratio = data.get("npk_ratio", "")
            reasoning = data.get("reasoning", "")

            response = f"**🌾 Fertilizer Recommendation: {fertilizer_name}**\n"
            if npk_ratio:
                response += f"NPK Ratio: {npk_ratio}\n"
            if reasoning:
                response += f"\n{reasoning}"

            return response

        elif agent_name == "crop_agent":
            recommended_crop = data.get("recommended_crop", "Unknown")
            confidence = data.get("confidence_percentage", 0)
            alternatives = data.get("alternatives", [])
            requested_count = data.get("requested_crop_count", 1)
            
            # Check if multi-crop response requested
            if requested_count > 1 and alternatives:
                response = f"**🌱 Top {requested_count} Recommended Crops**\n\n"
                response += f"1. **{recommended_crop.title()}** - {confidence:.1f}% confidence\n"
                
                # Add alternatives up to requested count
                for i, alt in enumerate(alternatives[:requested_count - 1], start=2):
                    crop_name = alt.get("crop", "Unknown")
                    crop_conf = alt.get("confidence_percentage", 0)
                    response += f"{i}. **{crop_name.title()}** - {crop_conf:.1f}% confidence\n"
                
                return response
            else:
                # Single crop response (default)
                response = f"**🌱 Recommended Crop: {recommended_crop.title()}**\n"
                response += f"Confidence: {confidence:.1f}%"
                return response

        elif agent_name == "disease_detection_agent":
            disease_name = data.get("disease_name", "Unknown")
            is_healthy = data.get("is_healthy", False)
            confidence = data.get("confidence_percentage", 0)

            if is_healthy:
                response = f"**✅ Good News! Your crop appears healthy**\n"
            else:
                response = f"**🔍 Disease Detected: {disease_name}**\n"

            response += f"Confidence: {confidence}%"

            return response

        elif agent_name == "weather_agent":
            location = data.get("location", "Unknown")
            temperature = data.get("temperature", 0)
            humidity = data.get("humidity", 0)
            description = data.get("description", "")

            response = f"**🌤️ Weather for {location}**\n"
            response += f"Temperature: {temperature}°C\n"
            response += f"Humidity: {humidity}%\n"
            response += f"Conditions: {description}"

            return response

        elif agent_name == "general_rag_agent":
            answer = data.get("answer", "")
            return answer

        else:
            # Unknown agent - return raw data
            return f"{agent_name}: {str(data)}"

    # ========================================================================
    # Helper Methods
    # ========================================================================

    def _is_greeting(self, query: str) -> bool:
        """Check if query is a greeting"""
        return any(re.search(pattern, query) for pattern in self.greeting_patterns)

    def _is_thanks(self, query: str) -> bool:
        """Check if query is a thank you"""
        return any(re.search(pattern, query) for pattern in self.thanks_patterns)

    def _extract_location_from_query(self, query: str) -> Optional[str]:
        """
        Extract location/place names from query (BUG FIX #4, #5)

        Recognizes Indian cities, states, and districts.
        Stores location in user_context for future use by agents.

        Args:
            query: User's query

        Returns:
            Location name if found, None otherwise

        Examples:
            "What crops grow in Bangalore?" → "Bangalore"
            "Weather in Mumbai" → "Mumbai"
            "Best crops for Punjab" → "Punjab"
        """
        # Common Indian cities and states (add more as needed)
        locations = [
            # Major cities
            "Mumbai", "Delhi", "Bangalore", "Bengaluru", "Hyderabad", "Chennai",
            "Kolkata", "Pune", "Ahmedabad", "Jaipur", "Surat", "Lucknow",
            "Kanpur", "Nagpur", "Indore", "Thane", "Bhopal", "Visakhapatnam",
            "Pimpri-Chinchwad", "Patna", "Vadodara", "Ghaziabad", "Ludhiana",
            "Agra", "Nashik", "Faridabad", "Meerut", "Rajkot", "Varanasi",

            # States
            "Maharashtra", "Karnataka", "Kerala", "Tamil Nadu", "Telangana",
            "Andhra Pradesh", "Gujarat", "Rajasthan", "Punjab", "Haryana",
            "Uttar Pradesh", "Madhya Pradesh", "West Bengal", "Bihar", "Odisha",

            # Districts/Agricultural regions
            "Vidarbha", "Marathwada", "Western Maharashtra", "Coastal Karnataka",
            "Malnad", "Konkan", "Deccan", "Bundelkhand"
        ]

        # Search for location in query (case-insensitive)
        query_lower = query.lower()
        for location in locations:
            if location.lower() in query_lower:
                logger.info(f"Location match found: {location}")
                return location

        return None

    def health_check(self) -> Dict[str, Any]:
        """
        Perform health check on supervisor

        Returns:
            Health status
        """
        return {
            "status": "healthy",
            "agent": "supervisor",
            "generation_service_available": self.generation_service is not None,
        }
