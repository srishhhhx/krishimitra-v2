"""
LangGraph Orchestrator V2 - Multi-Turn Conversation Support

This is the new orchestrator architecture with:
1. SupervisorAgent for plan decomposition and routing
2. Session management (load/save nodes)
3. Multi-turn clarification support
4. Clarification state management
5. Conditional routing based on clarification needs

Architecture:
    START
      ↓
    load_session  ← Restore user_context, conversation_history
      ↓
    supervisor  ← Brain: classify, plan, route, synthesize
      ↓
    [conditional routing]
      ↓
    fertilizer_agent | crop_agent | disease_agent | weather_agent | general_rag_agent
      ↓
    supervisor  ← Check clarification, continue plan, or synthesize
      ↓
    save_session  ← Persist state
      ↓
    END
"""

import time
from typing import Dict, Any, Optional
from langgraph.graph import StateGraph, END

from schemas.supervisor import SupervisorState, create_initial_supervisor_state
from agents.supervisor import SupervisorAgent
from agents.fertilizer_agent import FertilizerAgent
from services.generation import generation_service
from services.session_nodes import load_session_node, save_session_node
from core.logging import get_logger

logger = get_logger(__name__)


# ============================================================================
# Graph Nodes (All ASYNC for I/O-bound operations)
# ============================================================================


async def supervisor_node(state: SupervisorState) -> SupervisorState:
    """
    Node: Execute Supervisor Agent (ASYNC)

    The Supervisor is the brain that:
    - Classifies queries and creates agent plans (LLM call - ASYNC)
    - Routes to appropriate agents
    - Combines clarification requests
    - Detects interruptions
    - Prevents "I don't know" loops
    - Synthesizes final responses

    Why ASYNC?
    - Calls LLM for classification (500ms-1s)
    - Calls LLM for clarification extraction (300ms-800ms)
    - Non-blocking I/O enables concurrent request handling

    Args:
        state: SupervisorState

    Returns:
        Updated SupervisorState with next_agent or final_response
    """
    try:
        logger.info("Executing supervisor_node")

        supervisor = SupervisorAgent(generation_service=generation_service)
        state = await supervisor.run(state)  # ⚡ ASYNC - LLM calls

        return state

    except Exception as e:
        logger.error(f"Supervisor failed: {e}", exc_info=True)
        state["final_response"] = (
            "I encountered an issue processing your request. "
            "Please try again or rephrase your question."
        )
        state["is_active"] = False
        return state


async def fertilizer_agent_node(state: SupervisorState) -> SupervisorState:
    """
    Node: Execute Fertilizer Agent (ASYNC)

    Handles fertilizer recommendation with multi-turn clarification support.

    Why ASYNC?
    - Calls LLM for parameter extraction (200ms-500ms)
    - Tool execution is fast (<50ms) but LLM extraction is slow

    Args:
        state: SupervisorState (compatible with AgentState fields)

    Returns:
        Updated state with fertilizer_output or clarification_state
    """
    try:
        logger.info("Executing fertilizer_agent_node")

        fertilizer_agent = FertilizerAgent(generation_service=generation_service)

        # Convert SupervisorState → AgentState for agent execution
        # (SupervisorState is superset of AgentState)
        state = await fertilizer_agent.run(state)  # ⚡ ASYNC - LLM calls

        return state

    except Exception as e:
        logger.error(f"Fertilizer agent failed: {e}", exc_info=True)
        # Report error as structured finding
        if "collected_findings" not in state:
            state["collected_findings"] = {}

        state["collected_findings"]["fertilizer_agent"] = {
            "status": "error",
            "error": str(e),
            "agent": "fertilizer_agent"
        }
        return state


# Placeholder nodes for other agents (to be refactored in Phase 2)
# All marked as ASYNC for future compatibility

async def crop_agent_node(state: SupervisorState) -> SupervisorState:
    """Node: Execute Crop Agent (PLACEHOLDER - needs refactoring) (ASYNC)"""
    try:
        logger.info("Executing crop_agent_node (placeholder)")
        # TODO: Refactor CropAgent with BaseAgent pattern
        # For now, return error
        if "collected_findings" not in state:
            state["collected_findings"] = {}

        state["collected_findings"]["crop_agent"] = {
            "status": "error",
            "error": "Crop agent not yet refactored for V2",
            "agent": "crop_agent"
        }
        return state

    except Exception as e:
        logger.error(f"Crop agent failed: {e}", exc_info=True)
        state["collected_findings"]["crop_agent"] = {
            "status": "error",
            "error": str(e),
            "agent": "crop_agent"
        }
        return state


async def disease_detection_agent_node(state: SupervisorState) -> SupervisorState:
    """Node: Execute Disease Detection Agent (PLACEHOLDER - needs refactoring) (ASYNC)"""
    try:
        logger.info("Executing disease_detection_agent_node (placeholder)")
        # TODO: Refactor DiseaseDetectionAgent with BaseAgent pattern
        if "collected_findings" not in state:
            state["collected_findings"] = {}

        state["collected_findings"]["disease_detection_agent"] = {
            "status": "error",
            "error": "Disease detection agent not yet refactored for V2",
            "agent": "disease_detection_agent"
        }
        return state

    except Exception as e:
        logger.error(f"Disease detection agent failed: {e}", exc_info=True)
        state["collected_findings"]["disease_detection_agent"] = {
            "status": "error",
            "error": str(e),
            "agent": "disease_detection_agent"
        }
        return state


async def weather_agent_node(state: SupervisorState) -> SupervisorState:
    """Node: Execute Weather Agent (PLACEHOLDER - needs refactoring) (ASYNC)"""
    try:
        logger.info("Executing weather_agent_node (placeholder)")
        # TODO: Refactor WeatherAgent with BaseAgent pattern + error handling
        if "collected_findings" not in state:
            state["collected_findings"] = {}

        state["collected_findings"]["weather_agent"] = {
            "status": "error",
            "error": "Weather agent not yet refactored for V2",
            "agent": "weather_agent"
        }
        return state

    except Exception as e:
        logger.error(f"Weather agent failed: {e}", exc_info=True)
        state["collected_findings"]["weather_agent"] = {
            "status": "error",
            "error": str(e),
            "agent": "weather_agent"
        }
        return state


async def general_rag_agent_node(state: SupervisorState) -> SupervisorState:
    """Node: Execute General RAG Agent (PLACEHOLDER - needs wrapping) (ASYNC)"""
    try:
        logger.info("Executing general_rag_agent_node (placeholder)")
        # TODO: Wrap existing RAG pipeline
        if "collected_findings" not in state:
            state["collected_findings"] = {}

        state["collected_findings"]["general_rag_agent"] = {
            "status": "error",
            "error": "General RAG agent not yet wrapped for V2",
            "agent": "general_rag_agent"
        }
        return state

    except Exception as e:
        logger.error(f"General RAG agent failed: {e}", exc_info=True)
        state["collected_findings"]["general_rag_agent"] = {
            "status": "error",
            "error": str(e),
            "agent": "general_rag_agent"
        }
        return state


# ============================================================================
# Conditional Routing Function
# ============================================================================


def should_continue_or_clarify(state: SupervisorState) -> str:
    """
    Conditional routing function for Supervisor

    Decides next step based on:
    1. Clarification needs (any agent waiting for user input)
    2. Next agent in plan
    3. Plan completion

    Returns:
        - Agent name (e.g., "fertilizer_agent") if next agent in plan
        - "clarify" if any agent needs clarification
        - "end" if plan complete and no clarification needed

    Example:
        >>> state = {"clarification_state": {"fertilizer_agent": {...}}}
        >>> should_continue_or_clarify(state)
        "clarify"

        >>> state = {"next_agent": "crop_agent", "clarification_state": {}}
        >>> should_continue_or_clarify(state)
        "crop_agent"
    """
    # Check for clarification needs (highest priority)
    clarification_state = state.get("clarification_state", {})
    has_clarification = any(
        req is not None and req.get("needs_clarification")
        for req in clarification_state.values()
    )

    if has_clarification:
        logger.info("Routing to clarification (user input needed)")
        return "clarify"

    # Check if supervisor set next_agent
    next_agent = state.get("next_agent")
    if next_agent:
        logger.info(f"Routing to next agent: {next_agent}")
        return next_agent

    # Plan complete
    logger.info("Plan complete, routing to end")
    return "end"


# ============================================================================
# Orchestrator Graph V2
# ============================================================================


class OrchestratorGraphV2:
    """
    Multi-Turn Conversation Orchestrator (V2)

    New architecture with:
    - SupervisorAgent for planning and routing
    - Session management (load/save)
    - Multi-turn clarification support
    - Clarification state management
    - Conditional routing

    Example:
        >>> orchestrator = OrchestratorGraphV2()
        >>> result = orchestrator.run(
        ...     session_id="user-123",
        ...     user_query="What fertilizer should I use?"
        ... )
        >>> print(result["final_response"])
        "I need to know: 1. Your soil type 2. Your crop type"
    """

    def __init__(self):
        """Initialize orchestrator and build graph"""
        self.graph = self._build_graph()
        logger.info("OrchestratorGraphV2 initialized")

    def _build_graph(self) -> StateGraph:
        """
        Build the LangGraph workflow

        Workflow:
            START
              ↓
            load_session (restore user_context, conversation_history)
              ↓
            supervisor (classify, plan, route)
              ↓
            [conditional routing based on clarification/next_agent]
              ↓
            fertilizer_agent | crop_agent | disease_agent | weather_agent | general_rag_agent
              ↓
            supervisor (check clarification, continue, or synthesize)
              ↓
            [loop back to routing or end]
              ↓
            save_session (persist state)
              ↓
            END

        Returns:
            Compiled StateGraph
        """
        # Create graph with SupervisorState
        workflow = StateGraph(SupervisorState)

        # Add nodes
        workflow.add_node("load_session", load_session_node)
        workflow.add_node("supervisor", supervisor_node)
        workflow.add_node("fertilizer_agent", fertilizer_agent_node)
        workflow.add_node("crop_agent", crop_agent_node)
        workflow.add_node("disease_detection_agent", disease_detection_agent_node)
        workflow.add_node("weather_agent", weather_agent_node)
        workflow.add_node("general_rag_agent", general_rag_agent_node)
        workflow.add_node("save_session", save_session_node)

        # Define edges

        # Entry point
        workflow.set_entry_point("load_session")
        workflow.add_edge("load_session", "supervisor")

        # All agents route BACK to supervisor
        workflow.add_edge("fertilizer_agent", "supervisor")
        workflow.add_edge("crop_agent", "supervisor")
        workflow.add_edge("disease_detection_agent", "supervisor")
        workflow.add_edge("weather_agent", "supervisor")
        workflow.add_edge("general_rag_agent", "supervisor")

        # Supervisor has conditional routing
        workflow.add_conditional_edges(
            "supervisor",
            should_continue_or_clarify,
            {
                "fertilizer_agent": "fertilizer_agent",
                "crop_agent": "crop_agent",
                "disease_detection_agent": "disease_detection_agent",
                "weather_agent": "weather_agent",
                "general_rag_agent": "general_rag_agent",
                "clarify": "save_session",  # Return to user for clarification
                "end": "save_session"  # Return final answer
            }
        )

        # Save session before ending
        workflow.add_edge("save_session", END)

        # Compile graph
        # Note: LangGraph handles recursion internally; supervisor controls flow
        compiled_graph = workflow.compile()

        logger.info(
            "Graph compiled with nodes: load_session, supervisor, "
            "fertilizer_agent, crop_agent, disease_detection_agent, "
            "weather_agent, general_rag_agent, save_session"
        )

        return compiled_graph

    async def run(
        self,
        session_id: str,
        user_query: str,
        user_id: Optional[str] = None,
        preferred_language: str = "en",
    ) -> Dict[str, Any]:
        """
        Execute the orchestrator graph (ASYNC)

        Why ASYNC?
        - Supervisor and agents make LLM calls (500ms-2s)
        - Enables concurrent request handling at API level
        - Non-blocking I/O improves throughput (0.5 → 5-10 req/sec)

        Args:
            session_id: Unique session identifier for multi-turn conversations
            user_query: User's question
            user_id: Optional user identifier
            preferred_language: User's preferred language (default: "en")

        Returns:
            Orchestrator response with final_response, metadata, and latencies

        Example:
            >>> orchestrator = OrchestratorGraphV2()
            >>> result = await orchestrator.run(
            ...     session_id="user-123-abc",
            ...     user_query="What fertilizer for wheat?",
            ...     user_id="user-123"
            ... )
            >>> print(result["final_response"])
            "I need to know your soil type..."
        """
        start_time = time.perf_counter()

        try:
            # Initialize state
            initial_state = create_initial_supervisor_state(
                session_id=session_id,
                user_id=user_id or "anonymous",
                preferred_language=preferred_language
            )

            # Set current query
            initial_state["user_query"] = user_query

            logger.info(f"Executing orchestrator V2 for query: {user_query[:100]}...")

            # Execute graph with ASYNC invoke
            # LangGraph automatically handles async nodes with ainvoke()
            final_state = await self.graph.ainvoke(initial_state)  # ⚡ ASYNC

            # Calculate total latency
            total_latency_ms = (time.perf_counter() - start_time) * 1000

            logger.info(
                f"Orchestrator V2 completed: "
                f"latency={total_latency_ms:.0f}ms, "
                f"turn={final_state.get('turn_count', 0)}, "
                f"active={final_state.get('is_active', False)}"
            )

            # Format response
            return self._format_response(final_state, total_latency_ms)

        except Exception as e:
            logger.error(f"Orchestrator V2 execution failed: {e}", exc_info=True)
            raise

    def _format_response(
        self,
        state: SupervisorState,
        total_latency_ms: float
    ) -> Dict[str, Any]:
        """
        Format final state into API response

        Args:
            state: Final SupervisorState
            total_latency_ms: Total execution time

        Returns:
            Formatted response dictionary
        """
        return {
            "final_response": state.get("final_response", ""),
            "session_id": state.get("session_id", ""),
            "turn_count": state.get("turn_count", 0),
            "is_active": state.get("is_active", False),
            "agent_plan": state.get("agent_plan", []),
            "collected_findings": state.get("collected_findings", {}),
            "clarification_state": state.get("clarification_state", {}),
            "total_latency_ms": int(total_latency_ms),
            "metadata": {
                "conversation_turns": len(state.get("conversation_history", [])),
                "user_id": state.get("user_context", {}).get("user_id", "anonymous"),
            }
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
                    "id": "load_session",
                    "name": "LoadSession",
                    "type": "session",
                    "description": "Restore user context and conversation history"
                },
                {
                    "id": "supervisor",
                    "name": "Supervisor",
                    "type": "brain",
                    "description": "Classify, plan, route, and synthesize"
                },
                {
                    "id": "fertilizer_agent",
                    "name": "FertilizerAgent",
                    "type": "agent",
                    "description": "Fertilizer recommendations (V2 refactored)"
                },
                {
                    "id": "crop_agent",
                    "name": "CropAgent",
                    "type": "agent",
                    "description": "Crop recommendations (pending refactor)"
                },
                {
                    "id": "disease_detection_agent",
                    "name": "DiseaseDetectionAgent",
                    "type": "agent",
                    "description": "Disease detection (pending refactor)"
                },
                {
                    "id": "weather_agent",
                    "name": "WeatherAgent",
                    "type": "agent",
                    "description": "Weather information (pending refactor)"
                },
                {
                    "id": "general_rag_agent",
                    "name": "GeneralRAGAgent",
                    "type": "agent",
                    "description": "General knowledge (pending wrap)"
                },
                {
                    "id": "save_session",
                    "name": "SaveSession",
                    "type": "session",
                    "description": "Persist state for multi-turn conversations"
                },
            ],
            "edges": [
                {"source": "START", "target": "load_session"},
                {"source": "load_session", "target": "supervisor"},
                {"source": "supervisor", "target": "fertilizer_agent", "condition": "next_agent=fertilizer_agent"},
                {"source": "supervisor", "target": "crop_agent", "condition": "next_agent=crop_agent"},
                {"source": "supervisor", "target": "disease_detection_agent", "condition": "next_agent=disease_detection_agent"},
                {"source": "supervisor", "target": "weather_agent", "condition": "next_agent=weather_agent"},
                {"source": "supervisor", "target": "general_rag_agent", "condition": "next_agent=general_rag_agent"},
                {"source": "supervisor", "target": "save_session", "condition": "clarify OR end"},
                {"source": "fertilizer_agent", "target": "supervisor"},
                {"source": "crop_agent", "target": "supervisor"},
                {"source": "disease_detection_agent", "target": "supervisor"},
                {"source": "weather_agent", "target": "supervisor"},
                {"source": "general_rag_agent", "target": "supervisor"},
                {"source": "save_session", "target": "END"},
            ],
            "entry_point": "load_session",
            "description": "Multi-turn orchestrator with Supervisor brain: Load → Supervise → [Agents] → Supervise → Save"
        }

    def health_check(self) -> Dict[str, Any]:
        """
        Perform health check on the orchestrator V2

        Returns:
            Health status of orchestrator and components
        """
        try:
            # Check session store
            from core.session_store import get_session_store
            store = get_session_store()
            store_stats = store.get_stats()

            # Check supervisor
            supervisor = SupervisorAgent(generation_service=generation_service)
            supervisor_health = supervisor.health_check()

            # Check fertilizer agent
            fertilizer_agent = FertilizerAgent(generation_service=generation_service)
            fertilizer_health = fertilizer_agent.health_check()

            return {
                "status": "healthy",
                "version": "v2",
                "graph_compiled": True,
                "nodes": [
                    "load_session",
                    "supervisor",
                    "fertilizer_agent",
                    "crop_agent",
                    "disease_detection_agent",
                    "weather_agent",
                    "general_rag_agent",
                    "save_session"
                ],
                "session_store": store_stats,
                "supervisor": supervisor_health,
                "agents_status": {
                    "fertilizer_agent": fertilizer_health.get("status"),
                    "crop_agent": "pending_refactor",
                    "disease_detection_agent": "pending_refactor",
                    "weather_agent": "pending_refactor",
                    "general_rag_agent": "pending_wrap"
                }
            }

        except Exception as e:
            logger.error(f"Orchestrator V2 health check failed: {e}")
            return {"status": "error", "error": str(e)}


# ============================================================================
# Global Orchestrator V2 Instance
# ============================================================================

orchestrator_v2 = OrchestratorGraphV2()
