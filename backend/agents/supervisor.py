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
from typing import Dict, Any, List, Optional
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
                "Happy farming! 🌾"
            )
            state["is_active"] = False
            return state

        # BUG FIX #4: Extract location from query and store in user_context
        extracted_location = self._extract_location_from_query(state["user_query"])
        if extracted_location:
            if "user_context" not in state:
                state["user_context"] = {}
            state["user_context"]["location"] = extracted_location
            logger.info(f"LOCATION EXTRACTED: {extracted_location} → saved to user_context")

        # Classify and plan
        agent_plan = await self._classify_and_plan(query)

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

    async def _classify_and_plan(self, query: str) -> List[str]:
        """
        Classify query and create agent execution plan

        BUG FIX #1: Pre-classification pattern detection for explicit parameters
        - If query contains N/P/K parameters → route to crop_agent (not fertilizer!)
        - If query states crop preference → route to crop_agent
        - If query has location for crop → route to crop_agent
        - Then use LLM for complex queries

        Args:
            query: User's query

        Returns:
            List of agent names to execute in order

        Example:
            >>> plan = await supervisor._classify_and_plan("N=90 P=40 K=40 temp=25...")
            >>> plan
            ["crop_agent"]  # Direct routing based on explicit parameters
        """
        # BUG FIX #1: Pre-classification for explicit parameter patterns
        # This bypasses LLM for clear-cut cases to avoid misrouting

        # Pattern 1: Explicit NPK + environmental parameters (7 params for crop recommendation)
        param_pattern = r'(N|nitrogen)\s*[=:]\s*\d+.*(P|phosphorus)\s*[=:]\s*\d+.*(K|potassium)\s*[=:]\s*\d+'
        if re.search(param_pattern, query, re.IGNORECASE):
            logger.info(f"PRE-CLASSIFICATION: Detected explicit N/P/K parameters → crop_agent")
            return ["crop_agent"]

        # Pattern 2: User stating crop preference (e.g., "I want to grow wheat")
        crop_preference_pattern = r'\b(want|plan|planning|intend|like)\s+to\s+(grow|plant|cultivate)\s+\w+'
        if re.search(crop_preference_pattern, query, re.IGNORECASE):
            logger.info(f"PRE-CLASSIFICATION: Detected crop preference statement → crop_agent")
            return ["crop_agent"]

        # Pattern 3: Location-based crop queries (e.g., "crops in Bangalore")
        location_crop_pattern = r'(crops?|crop recommendation)\s+(in|for|at|near)\s+\w+'
        if re.search(location_crop_pattern, query, re.IGNORECASE):
            logger.info(f"PRE-CLASSIFICATION: Detected location-based crop query → crop_agent")
            return ["crop_agent"]

        # If no pre-classification match, use LLM for complex queries
        classification_prompt = f"""
Classify this agricultural query and determine which specialist(s) to call.

Query: "{query}"

Available specialists:
1. disease_detection_agent - Plant disease diagnosis, leaf spots, pests, crop health issues, plant diseases
2. fertilizer_agent - Fertilizer recommendations, NPK ratios, soil nutrition, manure, compost
3. crop_agent - Crop selection, planting advice, suitable crops for conditions
4. weather_agent - Weather forecasts, climate conditions, rainfall, temperature
5. general_rag_agent - General agriculture knowledge, best practices, farming techniques, other queries

Classification Rules:
- Disease/pest/health/spots/infection → disease_detection_agent (PRIORITY)
- Fertilizer/nutrition/NPK/manure → fertilizer_agent
- Crop selection/which crop/recommend crop → crop_agent
- Weather/forecast/climate → weather_agent
- General knowledge/how to/best practices → general_rag_agent
- Multiple intents → multiple agents in logical order

CRITICAL: Disease queries MUST route to disease_detection_agent, NOT general_rag_agent!

Return ONLY valid JSON:
{{"agents": ["agent_name1", "agent_name2"], "reasoning": "why these agents"}}

Examples:
- "My tomato leaves have brown spots" → {{"agents": ["disease_detection_agent"], "reasoning": "disease diagnosis"}}
- "What fertilizer for wheat?" → {{"agents": ["fertilizer_agent"], "reasoning": "fertilizer recommendation"}}
- "Best crop and fertilizer for black soil?" → {{"agents": ["crop_agent", "fertilizer_agent"], "reasoning": "crop selection then fertilizer"}}
"""

        try:
            # Call LLM for classification (sync method, no await)
            response, _ = self.generation_service.generate_answer(
                query=classification_prompt,
                retrieved_chunks=[],
                max_tokens=200,
                temperature=0.0
            )

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

            # Log classification with enhanced formatting
            workflow_log.log_classification(
                intent="multi_agent" if len(agent_plan) > 1 else (agent_plan[0] if agent_plan else "unknown"),
                agents=agent_plan,
                reasoning=reasoning
            )

            return agent_plan

        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse classification JSON: {e}. Response: {response}")
            return ["general_rag_agent"]

        except Exception as e:
            logger.error(f"Classification failed: {e}", exc_info=True)
            return ["general_rag_agent"]

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
            state["final_response"] = (
                "I couldn't find a suitable answer. Please try rephrasing your question."
            )
            state["is_active"] = False
            return state

        # Build response from findings
        response_parts = []

        # Process each agent's findings
        for agent_name, finding in collected_findings.items():
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
