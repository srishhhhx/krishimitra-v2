"""
LangGraph Orchestrator for Multi-Agent Coordination

This module implements the main orchestration layer that:
1. Classifies incoming queries
2. Routes to appropriate specialized agents
3. Synthesizes final responses
4. Tracks execution metrics
"""

import time
import asyncio
from typing import Dict, Any, Optional, Literal
from datetime import datetime
from langgraph.graph import StateGraph, END

from schemas.agents import AgentState, AgentIntent, create_example_state
from schemas.supervisor import SupervisorState, create_initial_supervisor_state
from services.query_classifier import query_classifier
from agents.base import GeneralRAGAgent
from core.workflow_logging import workflow_log
from agents.fertilizer_agent import FertilizerAgent
from agents.disease_detection_agent import DiseaseDetectionAgent
from agents.crop_agent import CropAgent
from agents.weather_agent import WeatherAgent
from agents.supervisor import SupervisorAgent
from services.embeddings import embedding_service
from services.retrieval import retrieval_service
from services.generation import generation_service
from core.session_store import get_session_store
from core.logging import get_logger
import uuid

logger = get_logger(__name__)

# Global session store instance
session_store = get_session_store()


# ============================================================================
# Async Helper Utilities
# ============================================================================


def run_async_agent(async_func, *args, **kwargs):
    """
    Run an async function, handling both sync and async contexts.

    This utility function detects if we're already in an event loop
    and uses the appropriate method to run the async function.

    Args:
        async_func: The async function to run
        *args: Positional arguments to pass to the function
        **kwargs: Keyword arguments to pass to the function

    Returns:
        The result of the async function
    """
    try:
        # Try to get the current event loop
        try:
            loop = asyncio.get_running_loop()
            # We're in an async context (event loop is running)
            # Create a new thread to run the async function
            import concurrent.futures
            import threading

            result = None
            exception = None

            def run_in_thread():
                nonlocal result, exception
                try:
                    # Create a new event loop for this thread
                    new_loop = asyncio.new_event_loop()
                    asyncio.set_event_loop(new_loop)
                    try:
                        result = new_loop.run_until_complete(async_func(*args, **kwargs))
                    finally:
                        new_loop.close()
                except Exception as e:
                    exception = e

            thread = threading.Thread(target=run_in_thread)
            thread.start()
            thread.join()

            if exception:
                raise exception
            return result

        except RuntimeError:
            # No event loop running, safe to use asyncio.run
            return asyncio.run(async_func(*args, **kwargs))

    except Exception as e:
        logger.error(f"Failed to run async agent: {e}", exc_info=True)
        raise


# ============================================================================
# Session Management Nodes (V2 Pattern)
# ============================================================================


def load_session_node(state: AgentState) -> AgentState:
    """
    Node: Load or create session state

    This is the NEW ENTRY POINT for the orchestrator (V2 pattern).

    Workflow:
    1. Check if session_id is provided in state
    2. If yes, try to load existing session from session_store
    3. If no or session not found, create new session
    4. Merge session state into AgentState

    Args:
        state: AgentState with user_query and optional session_id

    Returns:
        Updated state with session context loaded
    """
    try:
        # Get or generate session_id
        session_id = state.get("session_id")
        if not session_id:
            session_id = str(uuid.uuid4())
            state["session_id"] = session_id
            logger.info(f"Generated new session_id: {session_id}")

        # Try to load existing session
        supervisor_state = session_store.get(session_id)

        if supervisor_state:
            # Session found - merge into AgentState
            logger.info(f"Loaded existing session: {session_id} (turn {supervisor_state['turn_count']})")

            # Merge supervisor state fields into agent state
            state["user_context"] = supervisor_state.get("user_context", {})
            state["conversation_history"] = supervisor_state.get("conversation_history", [])
            state["clarification_state"] = supervisor_state.get("clarification_state", {})
            state["agent_plan"] = supervisor_state.get("agent_plan", [])
            state["collected_findings"] = supervisor_state.get("collected_findings", {})

            # Update turn count
            supervisor_state["turn_count"] = supervisor_state.get("turn_count", 0) + 1
            state["turn_count"] = supervisor_state["turn_count"]

        else:
            # No session found - create new
            logger.info(f"Creating new session: {session_id}")

            user_id = state.get("user_id", "default_user")
            preferred_language = state.get("preferred_language", "en")

            # Initialize new session state fields
            state["user_context"] = {
                "user_id": user_id,
                "preferred_language": preferred_language,
                "location": None,
                "soil_type": None,
                "crop_history": [],
                "mentioned_crops": [],
                "mentioned_diseases": [],
                "inferred_preferences": {},
            }
            state["conversation_history"] = []
            state["clarification_state"] = {}
            state["agent_plan"] = []
            state["collected_findings"] = {}
            state["turn_count"] = 1

        return state

    except Exception as e:
        logger.error(f"Session load failed: {e}", exc_info=True)
        # Fallback: continue with empty session
        state["session_id"] = str(uuid.uuid4())
        state["user_context"] = {}
        state["conversation_history"] = []
        state["clarification_state"] = {}
        state["agent_plan"] = []
        state["collected_findings"] = {}
        state["turn_count"] = 1
        return state


def save_session_node(state: AgentState) -> AgentState:
    """
    Node: Save session state to session store

    This node runs AFTER supervisor synthesizes final_response.

    Workflow:
    1. Extract supervisor-relevant fields from AgentState
    2. Create SupervisorState object
    3. Save to session_store

    Args:
        state: AgentState with session_id and updated context

    Returns:
        Unchanged state (save is side-effect)
    """
    try:
        # Debug: Check all state keys
        session_id = state.get("session_id")

        if not session_id:
            logger.warning(f"No session_id in state. Available keys: {list(state.keys())}")
            logger.warning("Skipping session save")
            return state

        # Build SupervisorState from AgentState
        supervisor_state: SupervisorState = {
            "session_id": session_id,
            "user_context": state.get("user_context", {}),
            "conversation_history": state.get("conversation_history", []),
            "clarification_state": state.get("clarification_state", {}),
            "combined_clarification": None,
            "current_query": state.get("user_query", ""),
            "current_query_timestamp": datetime.utcnow(),
            "orchestrator_result": {
                "final_response": state.get("final_response"),
                "collected_findings": state.get("collected_findings"),
                "executed_agents": state.get("executed_agents"),
                "total_latency_ms": state.get("total_latency_ms"),
            },
            "orchestrator_error": state.get("error"),
            "session_start_time": datetime.utcnow(),  # Will be preserved on next load if exists
            "turn_count": state.get("turn_count", 1),
            "is_active": state.get("is_active", True),
        }

        # Save to session store
        session_store.save(session_id, supervisor_state)

        # Auto-cleanup expired sessions
        session_store.auto_cleanup_if_needed()

        logger.info(f"Saved session: {session_id} (turn {supervisor_state['turn_count']})")

        return state

    except Exception as e:
        logger.error(f"Session save failed: {e}", exc_info=True)
        # Don't fail the request - just log the error
        return state


def supervisor_node(state: AgentState) -> AgentState:
    """
    Node: Execute Supervisor Agent

    The Supervisor is the "brain" that:
    1. Classifies queries and creates agent plans
    2. Routes to appropriate agents via next_agent field
    3. Handles clarification requests from agents
    4. Synthesizes final responses

    Args:
        state: AgentState with user_query and session context

    Returns:
        Updated state with next_agent or final_response
    """
    try:
        # Log supervisor execution start
        workflow_log.log_supervisor_start(state)

        # Create SupervisorAgent instance
        supervisor = SupervisorAgent(generation_service=generation_service)

        # Build SupervisorState from AgentState
        # (SupervisorAgent.run() expects SupervisorState)
        supervisor_state: SupervisorState = {
            "session_id": state.get("session_id", ""),
            "user_context": state.get("user_context", {}),
            "conversation_history": state.get("conversation_history", []),
            "clarification_state": state.get("clarification_state", {}),
            "combined_clarification": None,
            "current_query": state.get("user_query", ""),
            "current_query_timestamp": datetime.utcnow(),
            "orchestrator_result": None,
            "orchestrator_error": None,
            "session_start_time": datetime.utcnow(),
            "turn_count": state.get("turn_count", 1),
            "is_active": True,
            "agent_plan": state.get("agent_plan", []),
            "next_agent": state.get("next_agent"),
            "final_response": state.get("final_response"),
            "collected_findings": state.get("collected_findings", {}),
            "executed_agents": state.get("executed_agents", []),  # CRITICAL: Pass executed_agents
            "user_query": state.get("user_query", ""),
        }

        # Execute supervisor
        updated_supervisor_state = run_async_agent(supervisor.run, supervisor_state)

        # Merge supervisor state back into AgentState
        # IMPORTANT: Preserve session_id and turn_count from AgentState
        state["user_context"] = updated_supervisor_state.get("user_context", {})
        state["conversation_history"] = updated_supervisor_state.get("conversation_history", [])
        state["clarification_state"] = updated_supervisor_state.get("clarification_state", {})
        state["agent_plan"] = updated_supervisor_state.get("agent_plan", [])
        state["next_agent"] = updated_supervisor_state.get("next_agent")
        state["final_response"] = updated_supervisor_state.get("final_response")
        state["collected_findings"] = updated_supervisor_state.get("collected_findings", {})
        state["is_active"] = updated_supervisor_state.get("is_active", True)
        # session_id and turn_count are already set by load_session_node - don't overwrite

        # Log supervisor decision
        if state.get("next_agent"):
            workflow_log.log_routing("supervisor", state['next_agent'])
        elif state.get("final_response"):
            workflow_log.log_synthesis(
                state['final_response'],
                len(state['final_response'])
            )
            workflow_log.log_findings_summary(state.get("collected_findings", {}))

        return state

    except Exception as e:
        logger.error(f"Supervisor node failed: {e}", exc_info=True)
        state["error"] = f"supervisor: {str(e)}"
        state["final_response"] = (
            "I encountered an issue processing your request. "
            "Please try again or rephrase your question."
        )
        state["is_active"] = False
        return state


# ============================================================================
# Graph Nodes
# ============================================================================


def classify_intent_node(state: AgentState) -> AgentState:
    """
    Node: Classify user query intent

    This node determines which agent should handle the query by
    classifying the user's intent.

    Args:
        state: Current agent state with user_query

    Returns:
        Updated state with intent and confidence
    """
    try:
        query = state.get("user_query", "")
        if not query:
            state["error"] = "No query provided"
            state["intent"] = AgentIntent.GENERAL_RAG.value
            state["confidence"] = 0.0
            return state

        logger.info(f"Classifying query: {query[:100]}...")

        # Classify intent
        intent, confidence = query_classifier.classify(query)

        # Update state
        state["intent"] = intent.value
        state["confidence"] = confidence
        state["classification_method"] = "hybrid"

        logger.info(f"Intent classified: {intent.value} (confidence: {confidence:.2f})")

        return state

    except Exception as e:
        logger.error(f"Intent classification failed: {e}", exc_info=True)
        state["error"] = f"Classification error: {str(e)}"
        state["intent"] = AgentIntent.GENERAL_RAG.value
        state["confidence"] = 0.5
        return state


def general_rag_agent_node(state: AgentState) -> AgentState:
    """
    Node: Execute General RAG Agent

    This node handles general agricultural knowledge queries
    using the RAG pipeline (Embed -> Retrieve -> Generate).

    Args:
        state: Agent state with user_query

    Returns:
        Updated state with rag_output
    """
    try:
        # Log agent execution start
        workflow_log.log_agent_start("general_rag_agent", state.get("user_query", ""))

        rag_agent = GeneralRAGAgent(
            embedding_service=embedding_service,
            retrieval_service=retrieval_service,
            generation_service=generation_service,
        )
        state = run_async_agent(rag_agent.run, state)

        return state

    except Exception as e:
        logger.error(f"General RAG agent failed: {e}", exc_info=True)
        state["error"] = f"general_rag_agent: {str(e)}"
        return state


def fertilizer_agent_node(state: AgentState) -> AgentState:
    """
    Node: Execute Fertilizer Agent

    This node handles fertilizer recommendation queries using
    the XGBoost model via the FertilizerAgent.

    Args:
        state: Agent state with user_query

    Returns:
        Updated state with fertilizer_output
    """
    try:
        # Log agent execution start
        workflow_log.log_agent_start("fertilizer_agent", state.get("user_query", ""))

        fertilizer_agent = FertilizerAgent(generation_service=generation_service)
        state = run_async_agent(fertilizer_agent.run, state)

        return state

    except Exception as e:
        logger.error(f"Fertilizer agent failed: {e}", exc_info=True)
        state["error"] = f"fertilizer_agent: {str(e)}"
        return state


def disease_detection_agent_node(state: AgentState) -> AgentState:
    """
    Node: Execute Disease Detection Agent

    This node handles disease detection queries using the
    TensorFlow/Keras CNN model via the DiseaseDetectionAgent.

    Args:
        state: Agent state with images (required)

    Returns:
        Updated state with disease_output
    """
    try:
        # Log agent execution start
        workflow_log.log_agent_start("disease_detection_agent", state.get("user_query", ""))

        disease_agent = DiseaseDetectionAgent(generation_service=generation_service)
        state = run_async_agent(disease_agent.run, state)

        return state

    except Exception as e:
        logger.error(f"Disease detection agent failed: {e}", exc_info=True)
        state["error"] = f"disease_detection_agent: {str(e)}"
        return state


def crop_agent_node(state: AgentState) -> AgentState:
    """
    Node: Execute Crop Recommendation Agent

    This node handles crop recommendation queries using the
    Naive Bayes model via the CropAgent.

    Args:
        state: Agent state with user_query

    Returns:
        Updated state with crop_output
    """
    try:
        # Log agent execution start
        workflow_log.log_agent_start("crop_agent", state.get("user_query", ""))

        crop_agent = CropAgent(generation_service=generation_service)
        state = run_async_agent(crop_agent.run, state)

        return state

    except Exception as e:
        logger.error(f"Crop agent failed: {e}", exc_info=True)
        state["error"] = f"crop_agent: {str(e)}"
        return state


def weather_agent_node(state: AgentState) -> AgentState:
    """
    Node: Execute Weather Agent

    This node handles weather queries using the MCP weather server
    via the WeatherAgent.

    Args:
        state: Agent state with user_query

    Returns:
        Updated state with weather_output
    """
    try:
        # Log agent execution start
        workflow_log.log_agent_start("weather_agent", state.get("user_query", ""))

        weather_agent = WeatherAgent(generation_service=generation_service)
        state = run_async_agent(weather_agent.run, state)

        return state

    except Exception as e:
        logger.error(f"Weather agent failed: {e}", exc_info=True)
        state["error"] = f"weather_agent: {str(e)}"
        return state


def synthesize_response_node(state: AgentState) -> AgentState:
    """
    Node: Synthesize final response from agent outputs

    This node combines results from executed agents into a
    final user-facing response.

    Args:
        state: Agent state with agent outputs

    Returns:
        Updated state with final answer and metadata
    """
    try:
        logger.info("Synthesizing final response")

        # Check for errors
        if state.get("error"):
            state["answer"] = (
                "I encountered an issue processing your request. "
                "Please try again or rephrase your question."
            )
            state["metadata"] = {"error": state["error"]}
            return state

        # Handle fertilizer agent output
        if state.get("fertilizer_output"):
            output = state["fertilizer_output"]

            # Check if clarification is needed
            if output.get("needs_clarification"):
                state["answer"] = output["question"]
                state["metadata"] = {
                    "needs_clarification": True,
                    "extracted_so_far": output.get("extracted_so_far", {}),
                    "missing_parameters": output.get("missing_parameters", []),
                    "agent_used": "fertilizer_agent",
                }
                return state

            # Check for errors in tool execution
            if output.get("error"):
                state["answer"] = (
                    f"I couldn't process your fertilizer request: {output['error']}"
                )
                state["metadata"] = {"agent_used": "fertilizer_agent", "error": True}
                return state

            # Format successful fertilizer recommendation
            fertilizer_name = output.get("fertilizer_name", "Unknown")
            npk_ratio = output.get("npk_ratio", "")
            reasoning = output.get("reasoning", "")
            params_used = output.get("parameters_used", {})

            answer = f"**Fertilizer Recommendation: {fertilizer_name}**\n\n"

            if npk_ratio:
                answer += f"NPK Ratio: {npk_ratio}\n\n"

            if reasoning:
                answer += f"Why this fertilizer?\n{reasoning}\n\n"

            # Add parameters for transparency
            if params_used:
                answer += f"Based on your conditions:\n"
                answer += f"  - Soil Type: {params_used.get('soil_type', 'N/A')}\n"
                answer += f"  - Crop Type: {params_used.get('crop_type', 'N/A')}\n"
                answer += (
                    f"  - Temperature: {params_used.get('temperature', 'N/A')}°C\n"
                )
                answer += f"  - Humidity: {params_used.get('humidity', 'N/A')}%\n"
                answer += f"  - Nitrogen: {params_used.get('nitrogen', 'N/A')} kg/ha\n"
                answer += (
                    f"  - Phosphorous: {params_used.get('phosphorous', 'N/A')} kg/ha\n"
                )
                answer += (
                    f"  - Potassium: {params_used.get('potassium', 'N/A')} kg/ha\n"
                )

            state["answer"] = answer
            state["metadata"] = {
                "agent_used": "fertilizer_agent",
                "fertilizer_name": fertilizer_name,
                "npk_ratio": npk_ratio,
            }
            return state

        # Handle disease detection agent output
        if state.get("disease_output"):
            output = state["disease_output"]

            # Check for errors in detection
            if output.get("error"):
                state["answer"] = f"Disease Detection Issue: {output['error']}"
                if output.get("help"):
                    state["answer"] += f"\n\n{output['help']}"
                state["metadata"] = {
                    "agent_used": "disease_detection_agent",
                    "error": True,
                }
                return state

            # Format successful disease detection result
            disease_name = output.get("disease_name", "Unknown")
            crop = output.get("crop", "Unknown")
            is_healthy = output.get("is_healthy", False)
            confidence = output.get("confidence_percentage", 0)
            severity = output.get("severity", "unknown")
            treatment = output.get("treatment", "")
            preventive_measures = output.get("preventive_measures", [])

            if is_healthy:
                answer = f"**Good News! Your {crop} appears healthy.**\n\n"
                answer += f"Confidence: {confidence}%\n\n"
                answer += f"{treatment}\n\n"
                if preventive_measures:
                    answer += "**Preventive Care:**\n"
                    for measure in preventive_measures:
                        answer += f"  - {measure}\n"
            else:
                answer = f"**Disease Detected: {disease_name}**\n\n"
                answer += f"Crop: {crop}\n"
                answer += f"Confidence: {confidence}%\n"
                answer += f"Severity: {severity.capitalize()}\n\n"
                answer += f"**Treatment Recommendations:**\n{treatment}\n\n"
                if preventive_measures:
                    answer += "**Preventive Measures:**\n"
                    for measure in preventive_measures:
                        answer += f"  - {measure}\n"

            # Add crop type validation message if relevant
            crop_match = output.get("crop_type_match", {})
            if crop_match.get("match") is False:
                answer += f"\n⚠️ {crop_match.get('message', '')}\n"

            state["answer"] = answer
            state["metadata"] = {
                "agent_used": "disease_detection_agent",
                "disease_name": disease_name,
                "crop": crop,
                "is_healthy": is_healthy,
                "severity": severity,
                "confidence": confidence,
            }
            return state

        # Handle weather agent output
        if state.get("weather_output"):
            output = state["weather_output"]

            # Check if clarification is needed
            if output.get("needs_clarification"):
                state["answer"] = output.get("question", "Which location would you like weather information for?")
                state["metadata"] = {
                    "needs_clarification": True,
                    "agent_used": "weather_agent",
                }
                return state

            # Check for errors in weather retrieval
            if output.get("error"):
                state["answer"] = f"Weather Information Issue: {output['error']}"
                state["metadata"] = {
                    "agent_used": "weather_agent",
                    "error": True,
                }
                return state

            # Format successful weather information
            location = output.get("location", "Unknown")
            location_queried = output.get("location_queried", location)
            temperature = output.get("temperature", 0)
            humidity = output.get("humidity", 0)
            wind_speed = output.get("wind_speed", 0)
            description = output.get("description", "")
            agricultural_insights = output.get("agricultural_insights", "")

            answer = f"**🌤️ Weather Information for {location}**\n\n"

            # Current conditions
            answer += f"**Current Conditions:**\n"
            answer += f"  • Temperature: {temperature}°C\n"
            answer += f"  • Humidity: {humidity}%\n"
            answer += f"  • Wind Speed: {wind_speed} km/h\n"
            answer += f"  • Conditions: {description}\n\n"

            # Agricultural insights
            if agricultural_insights:
                answer += f"**Agricultural Advisory:**\n{agricultural_insights}\n\n"

            # Cache information (if available)
            cache_age = output.get("cache_age_minutes")
            if cache_age is not None:
                answer += f"*Data cached {cache_age} minute(s) ago*\n"

            state["answer"] = answer
            state["metadata"] = {
                "agent_used": "weather_agent",
                "location": location,
                "temperature": temperature,
                "humidity": humidity,
                "description": description,
            }
            return state

        # Handle crop recommendation agent output
        if state.get("crop_output"):
            output = state["crop_output"]

            # Check for errors in recommendation
            if output.get("error"):
                state["answer"] = f"Crop Recommendation Issue: {output['error']}"
                if output.get("needs_clarification"):
                    state["answer"] += "\n\nPlease provide more details about your soil and climate conditions."
                    extracted = output.get("extracted_params", {})
                    if any(v is not None for v in extracted.values()):
                        state["answer"] += "\n\nI detected the following parameters from your query:\n"
                        for param, value in extracted.items():
                            if value is not None:
                                state["answer"] += f"  - {param}: {value}\n"
                state["metadata"] = {
                    "agent_used": "crop_agent",
                    "error": True,
                }
                return state

            # Format successful crop recommendation
            recommended_crop = output.get("recommended_crop", "Unknown")
            confidence = output.get("confidence_percentage", 0)
            alternatives = output.get("alternatives", [])
            defaults_applied = output.get("defaults_applied", [])
            input_params = output.get("input_parameters", {})

            answer = f"**🌾 Recommended Crop: {recommended_crop.title()}**\n\n"
            answer += f"**Confidence:** {confidence:.1f}%\n\n"

            # Show alternative recommendations
            if alternatives and len(alternatives) > 0:
                answer += "**Alternative Crops:**\n"
                for alt in alternatives[:4]:  # Show top 4 alternatives
                    crop_name = alt.get("crop", "Unknown")
                    alt_confidence = alt.get("confidence_percentage", 0)
                    answer += f"  • {crop_name.title()} ({alt_confidence:.1f}%)\n"
                answer += "\n"

            # Show parameters used with transparency about defaults
            answer += "**Parameters Used:**\n"
            param_labels = {
                "nitrogen": "Nitrogen (N)",
                "phosphorus": "Phosphorus (P)",
                "potassium": "Potassium (K)",
                "temperature": "Temperature",
                "humidity": "Humidity",
                "ph": "Soil pH",
                "rainfall": "Rainfall"
            }

            for key, label in param_labels.items():
                value = input_params.get(key)
                if value is not None:
                    # Check if this was a default value
                    param_name = key.upper() if key in ["nitrogen", "phosphorus", "potassium"] else key
                    if key == "nitrogen":
                        param_name = "N"
                    elif key == "phosphorus":
                        param_name = "P"
                    elif key == "potassium":
                        param_name = "K"

                    if defaults_applied and param_name in defaults_applied:
                        answer += f"  • {label}: {value} *(default)*\n"
                    else:
                        answer += f"  • {label}: {value}\n"

            # Add note about defaults if any were used
            if defaults_applied and len(defaults_applied) > 0:
                answer += f"\n*Note: Default values were used for {len(defaults_applied)} parameter(s) "
                answer += "as they weren't specified in your query.*\n"

            state["answer"] = answer
            state["metadata"] = {
                "agent_used": "crop_agent",
                "recommended_crop": recommended_crop,
                "confidence": confidence,
                "alternatives": [alt.get("crop") for alt in alternatives[:4]],
                "defaults_applied": defaults_applied,
            }
            return state

        # Handle general RAG output
        if state.get("rag_output"):
            rag_output = state["rag_output"]
            state["answer"] = rag_output.get("answer", "")
            state["sources"] = rag_output.get("sources", [])

            # Combine latencies
            if state.get("latencies") is None:
                state["latencies"] = {}

            node_latencies = rag_output.get("node_latencies", {})
            state["latencies"].update(node_latencies)

            state["metadata"] = {
                "agent_used": "general_rag_agent",
                "num_chunks": len(rag_output.get("chunks", [])),
                "num_sources": len(rag_output.get("sources", [])),
            }
            return state

        # No agent output
        state["answer"] = (
            "I couldn't find a suitable answer. Please try rephrasing your question."
        )
        state["metadata"] = {"reason": "no_agent_output"}

        logger.info(f"Response synthesized: {len(state.get('answer', ''))} chars")

        return state

    except Exception as e:
        logger.error(f"Response synthesis failed: {e}", exc_info=True)
        state["error"] = f"Synthesis error: {str(e)}"
        state["answer"] = (
            "I encountered an issue generating the response. Please try again."
        )
        return state


# ============================================================================
# Orchestrator Graph
# ============================================================================


class OrchestratorGraph:
    """
    Main orchestrator for multi-agent system

    This class builds and manages the LangGraph workflow that:
    1. Classifies user intent
    2. Routes to appropriate agents
    3. Synthesizes responses
    4. Tracks execution metrics

    Example:
        >>> orchestrator = OrchestratorGraph()
        >>> result = orchestrator.run("What crop should I plant?")
        >>> print(result["answer"])
        "For crop recommendations, consider..."
    """

    def __init__(self):
        """Initialize orchestrator and build graph"""
        self.graph = self._build_graph()
        logger.info("OrchestratorGraph initialized")

    def _build_graph(self) -> StateGraph:
        """
        Build the LangGraph workflow (V2 Pattern with Supervisor)

        NEW Workflow:
            START
              ↓
            load_session (NEW ENTRY POINT)
              ↓
            supervisor (Brain - plans, routes, synthesizes)
              ↓
            [conditional routing based on supervisor's next_agent]
              ↓
            general_rag_agent | fertilizer_agent | disease_detection | crop_agent | weather_agent
              ↓
            supervisor (back to supervisor after each agent)
              ↓
            save_session
              ↓
            END

        Key Changes:
        - Entry point: load_session (not classify_intent)
        - Supervisor is the only router (holds agent_plan, sets next_agent)
        - All specialist agents return to supervisor (not synthesize_response)
        - Supervisor synthesizes final_response when plan complete
        - save_session runs after supervisor completes

        Returns:
            Compiled StateGraph
        """
        # Create graph
        workflow = StateGraph(AgentState)

        # ============================================================================
        # Add Nodes (V2 Pattern)
        # ============================================================================

        # Session management
        workflow.add_node("load_session", load_session_node)
        workflow.add_node("save_session", save_session_node)

        # Supervisor (brain)
        workflow.add_node("supervisor", supervisor_node)

        # Specialist agents
        workflow.add_node("general_rag_agent", general_rag_agent_node)
        workflow.add_node("fertilizer_agent", fertilizer_agent_node)
        workflow.add_node("disease_detection_agent", disease_detection_agent_node)
        workflow.add_node("crop_agent", crop_agent_node)
        workflow.add_node("weather_agent", weather_agent_node)

        # ============================================================================
        # Define Conditional Routing Function (V2 Pattern)
        # ============================================================================

        def supervisor_router(state: AgentState) -> str:
            """
            Route based on Supervisor's decision

            Routing Logic:
            1. If error → save_session (end flow)
            2. If final_response is set → save_session (supervisor finished)
            3. If next_agent is set → route to that specialist agent
            4. Fallback → save_session (should not happen)

            Args:
                state: AgentState with next_agent or final_response

            Returns:
                Next node name
            """
            # Check for errors
            if state.get("error"):
                logger.warning(f"Error detected, routing to save_session: {state['error']}")
                return "save_session"

            # Check if supervisor finished (final_response is set)
            if state.get("final_response"):
                logger.info("Supervisor completed, routing to save_session")
                return "save_session"

            # Route to specialist agent
            next_agent = state.get("next_agent")
            if next_agent:
                logger.info(f"Supervisor routing to specialist: {next_agent}")
                return next_agent

            # Fallback (should not happen - supervisor should always set next_agent or final_response)
            logger.warning("No next_agent or final_response set by supervisor, defaulting to save_session")
            return "save_session"

        # ============================================================================
        # Define Edges (V2 Pattern)
        # ============================================================================

        # Entry point: load_session
        workflow.set_entry_point("load_session")

        # load_session → supervisor
        workflow.add_edge("load_session", "supervisor")

        # Supervisor conditional routing
        workflow.add_conditional_edges(
            "supervisor",
            supervisor_router,
            {
                "save_session": "save_session",
                "general_rag_agent": "general_rag_agent",
                "fertilizer_agent": "fertilizer_agent",
                "disease_detection_agent": "disease_detection_agent",
                "crop_agent": "crop_agent",
                "weather_agent": "weather_agent",
            },
        )

        # All specialist agents return to supervisor
        workflow.add_edge("general_rag_agent", "supervisor")
        workflow.add_edge("fertilizer_agent", "supervisor")
        workflow.add_edge("disease_detection_agent", "supervisor")
        workflow.add_edge("crop_agent", "supervisor")
        workflow.add_edge("weather_agent", "supervisor")

        # save_session → END
        workflow.add_edge("save_session", END)

        # Compile graph
        logger.info(
            "Graph compiled (V2 Pattern): "
            "load_session → supervisor → [specialist agents] → supervisor → save_session → END"
        )
        return workflow.compile()

    def run(
        self,
        query: str,
        user_context: Optional[Dict[str, Any]] = None,
        images: Optional[list] = None,
        session_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Execute the orchestrator graph

        Args:
            query: User's question
            user_context: Optional context (location, language, etc.)
            images: Optional images for disease detection
            session_id: Optional session ID for multi-turn conversations

        Returns:
            Orchestrator response with answer, sources, and metrics

        Example:
            >>> orchestrator = OrchestratorGraph()
            >>> result = orchestrator.run(
            ...     query="What fertilizer for wheat?",
            ...     user_context={"location": "Punjab"},
            ...     session_id="abc-123"
            ... )
            >>> print(result["intent"])
            "fertilizer_advice"
        """
        start_time = time.perf_counter()

        # Log request start with beautiful formatting
        workflow_log.log_request_start(query, session_id, images)

        try:
            # Initialize state (V2 Pattern)
            initial_state: AgentState = {
                "user_query": query,
                "user_context": user_context or {},
                "conversation_history": [],
                "images": images,

                # Classification fields (legacy, may still be used by agents)
                "intent": None,
                "confidence": None,
                "classification_method": None,

                # Agent output fields (legacy, for backward compatibility)
                "rag_output": None,
                "crop_output": None,
                "fertilizer_output": None,
                "disease_output": None,
                "weather_output": None,

                # Supervisor V2 Pattern fields
                "agent_plan": [],
                "next_agent": None,
                "final_response": None,
                "collected_findings": {},
                "clarification_state": {},

                # Final response fields
                "answer": None,
                "metadata": None,
                "sources": None,

                # Execution tracking
                "latencies": {},
                "total_latency_ms": None,
                "executed_agents": [],

                # Error handling
                "error": None,
                "fallback_used": False,

                # Session fields (will be set by load_session_node)
                "session_id": session_id,  # Pass session_id from parameter to enable multi-turn conversations
                "turn_count": None,
                "is_active": None,
            }

            logger.info(f"Executing orchestrator (V2) for query: {query[:100]}...")

            # Execute graph (V2 pattern: load_session → supervisor → agents → supervisor → save_session)
            final_state = self.graph.invoke(initial_state)

            # Calculate total latency
            total_latency_ms = (time.perf_counter() - start_time) * 1000
            final_state["total_latency_ms"] = total_latency_ms

            # Log execution metrics
            metadata = final_state.get("metadata") or {}
            latencies = final_state.get("latencies") or {}

            logger.log_query_metrics(
                query=query,
                total_latency_ms=total_latency_ms,
                retrieval_latency_ms=latencies.get("retrieve_ms", 0),
                generation_latency_ms=latencies.get("generate_ms", 0),
                num_chunks=metadata.get("num_chunks", 0),
                success=not bool(final_state.get("error")),
            )

            # Log request completion with summary
            workflow_log.log_request_complete(
                session_id=final_state.get("session_id", "unknown"),
                latency_ms=total_latency_ms,
                executed_agents=final_state.get("executed_agents", [])
            )

            # Format response
            return self._format_response(final_state)

        except Exception as e:
            logger.error(f"Orchestrator execution failed: {e}", exc_info=True)
            raise

    def _format_response(self, state: AgentState) -> Dict[str, Any]:
        """
        Format final state into API response (V2 Pattern)

        V2 Pattern Changes:
        - Prioritize final_response (from supervisor) over answer (legacy)
        - Include collected_findings for debugging
        - Include session_id for multi-turn conversations

        Args:
            state: Final agent state

        Returns:
            Formatted response dictionary
        """
        # V2: Use final_response if set by supervisor, otherwise fall back to answer
        final_response = state.get("final_response") or state.get("answer", "")

        return {
            # V2: final_response is primary field
            "answer": final_response,
            "final_response": final_response,

            # Session and routing info
            "session_id": state.get("session_id"),
            "is_active": state.get("is_active"),
            "turn_count": state.get("turn_count"),

            # Classification (may be None in V2 if supervisor handles routing)
            "intent": state.get("intent", "unknown"),
            "confidence": state.get("confidence"),

            # Execution tracking
            "sources": state.get("sources", []),
            "executed_agents": state.get("executed_agents", []),
            "total_latency_ms": int(state.get("total_latency_ms", 0)),
            "node_latencies": state.get("latencies", {}),

            # V2: Collected findings from all agents
            "collected_findings": state.get("collected_findings", {}),

            # Metadata
            "metadata": state.get("metadata", {}),

            # Error handling
            "error": state.get("error"),
            "fallback_used": state.get("fallback_used", False),

            # Legacy: Include agent-specific outputs for backward compatibility
            "fertilizer_output": state.get("fertilizer_output"),
            "disease_output": state.get("disease_output"),
            "crop_output": state.get("crop_output"),
            "weather_output": state.get("weather_output"),
            "rag_output": state.get("rag_output"),
        }

    def get_graph_structure(self) -> Dict[str, Any]:
        """
        Get the graph structure for visualization

        Returns:
            Graph structure with nodes and edges
        """
        return {
            "nodes": [
                {
                    "id": "classify_intent",
                    "name": "ClassifyIntent",
                    "type": "classification",
                    "description": "Classify user query intent",
                },
                {
                    "id": "general_rag_agent",
                    "name": "GeneralRAGAgent",
                    "type": "agent",
                    "description": "Handle general agricultural knowledge queries",
                },
                {
                    "id": "fertilizer_agent",
                    "name": "FertilizerAgent",
                    "type": "agent",
                    "description": "Provide fertilizer recommendations",
                },
                {
                    "id": "disease_detection_agent",
                    "name": "DiseaseDetectionAgent",
                    "type": "agent",
                    "description": "Detect crop diseases from images",
                },
                {
                    "id": "crop_agent",
                    "name": "CropAgent",
                    "type": "agent",
                    "description": "Provide crop recommendations based on soil and climate",
                },
                {
                    "id": "weather_agent",
                    "name": "WeatherAgent",
                    "type": "agent",
                    "description": "Provide real-time weather information via MCP server",
                },
                {
                    "id": "synthesize_response",
                    "name": "SynthesizeResponse",
                    "type": "synthesis",
                    "description": "Combine agent outputs into final response",
                },
            ],
            "edges": [
                {"source": "START", "target": "classify_intent", "condition": None},
                {
                    "source": "classify_intent",
                    "target": "general_rag_agent",
                    "condition": "intent=general_rag",
                },
                {
                    "source": "classify_intent",
                    "target": "fertilizer_agent",
                    "condition": "intent=fertilizer_advice",
                },
                {
                    "source": "classify_intent",
                    "target": "disease_detection_agent",
                    "condition": "intent=disease_detection",
                },
                {
                    "source": "classify_intent",
                    "target": "crop_agent",
                    "condition": "intent=crop_recommendation",
                },
                {
                    "source": "classify_intent",
                    "target": "weather_agent",
                    "condition": "intent=weather_query",
                },
                {
                    "source": "general_rag_agent",
                    "target": "synthesize_response",
                    "condition": None,
                },
                {
                    "source": "fertilizer_agent",
                    "target": "synthesize_response",
                    "condition": None,
                },
                {
                    "source": "disease_detection_agent",
                    "target": "synthesize_response",
                    "condition": None,
                },
                {
                    "source": "crop_agent",
                    "target": "synthesize_response",
                    "condition": None,
                },
                {
                    "source": "weather_agent",
                    "target": "synthesize_response",
                    "condition": None,
                },
                {"source": "synthesize_response", "target": "END", "condition": None},
            ],
            "entry_point": "classify_intent",
            "description": "Multi-agent orchestrator with conditional routing: Classify → [RAG|Fertilizer|Disease|Crop|Weather] → Synthesize",
        }

    def health_check(self) -> Dict[str, Any]:
        """
        Perform health check on the orchestrator

        Returns:
            Health status of orchestrator and components
        """
        try:
            # Test with a simple query
            test_state: AgentState = create_example_state(query="test health check")

            # Test classification
            test_state = classify_intent_node(test_state)

            if test_state.get("error"):
                return {
                    "status": "unhealthy",
                    "error": test_state["error"],
                    "component": "classifier",
                }

            # Check classifier
            classifier_stats = query_classifier.get_classification_stats()

            # Check agent health
            fertilizer_agent = FertilizerAgent(generation_service=generation_service)
            fertilizer_health = fertilizer_agent.health_check()

            disease_agent = DiseaseDetectionAgent(generation_service=generation_service)
            disease_health = disease_agent.health_check()

            crop_agent = CropAgent(generation_service=generation_service)
            crop_health = crop_agent.health_check()

            weather_agent = WeatherAgent(generation_service=generation_service)
            weather_health = weather_agent.health_check()

            return {
                "status": "healthy",
                "graph_compiled": True,
                "nodes": [
                    "classify_intent",
                    "general_rag_agent",
                    "fertilizer_agent",
                    "disease_detection_agent",
                    "crop_agent",
                    "weather_agent",
                    "synthesize_response",
                ],
                "classifier": classifier_stats,
                "agents_available": {
                    "general_rag": True,
                    "fertilizer_advice": True,
                    "disease_detection": True,
                    "crop_recommendation": crop_health.get("status") == "healthy",
                    "weather_query": weather_health.get("status") == "healthy",
                },
                "agents": {
                    "general_rag": {"status": "healthy"},
                    "fertilizer": fertilizer_health,
                    "disease_detection": disease_health,
                    "crop": crop_health,
                    "weather": weather_health,
                },
            }

        except Exception as e:
            logger.error(f"Orchestrator health check failed: {e}")
            return {"status": "error", "error": str(e)}


# ============================================================================
# Global Orchestrator Instance
# ============================================================================

orchestrator = OrchestratorGraph()
