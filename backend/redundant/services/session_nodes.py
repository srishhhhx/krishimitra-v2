"""
Session Management Nodes for LangGraph Orchestrator

These nodes handle loading and saving supervisor state from/to the session store,
enabling multi-turn conversations with memory persistence.
"""

from datetime import datetime
from typing import Dict, Any

from schemas.supervisor import SupervisorState, create_empty_clarification_state
from core.session_store import get_session_store
from core.logging import get_logger

logger = get_logger(__name__)


def load_session_node(state: SupervisorState) -> SupervisorState:
    """
    Load session from store if session_id exists

    This node is executed at the START of the orchestrator workflow.
    It restores previous conversation state for multi-turn interactions.

    Restores:
    - user_context (long-term memory: soil_type, crop_type, location, etc.)
    - conversation_history (recent turns for context)
    - clarification_state (if mid-clarification)
    - turn_count (for statistics)

    Args:
        state: SupervisorState with session_id

    Returns:
        Updated state with restored session data or fresh state if new session

    Example:
        >>> state = {"session_id": "abc-123", "user_query": "sandy soil"}
        >>> state = load_session_node(state)
        >>> # State now has user_context from previous turns
    """
    session_id = state.get("session_id")

    if not session_id:
        # New session - initialize with defaults
        logger.info("No session_id provided - starting fresh session")
        state["turn_count"] = 0
        state["is_active"] = True
        state["conversation_history"] = []
        state["user_context"] = state.get("user_context", {})
        state["clarification_state"] = create_empty_clarification_state()
        state["collected_findings"] = {}
        state["agent_plan"] = []
        return state

    try:
        store = get_session_store()
        previous_state = store.get(session_id)

        if previous_state:
            # Restore persistent fields from previous session
            state["user_context"] = previous_state.get("user_context", {})
            state["conversation_history"] = previous_state.get("conversation_history", [])
            state["clarification_state"] = previous_state.get("clarification_state", create_empty_clarification_state())
            state["turn_count"] = previous_state.get("turn_count", 0)
            state["agent_plan"] = previous_state.get("agent_plan", [])
            state["collected_findings"] = previous_state.get("collected_findings", {})

            logger.info(
                f"Restored session {session_id} "
                f"(turn {state['turn_count']}, "
                f"history: {len(state['conversation_history'])} turns)"
            )

            # Trigger auto-cleanup if needed
            store.auto_cleanup_if_needed()

        else:
            # Session not found or expired - start fresh
            logger.info(f"Session {session_id} not found or expired - starting fresh")
            state["turn_count"] = 0
            state["is_active"] = True
            state["conversation_history"] = []
            state["user_context"] = state.get("user_context", {})
            state["clarification_state"] = create_empty_clarification_state()
            state["collected_findings"] = {}
            state["agent_plan"] = []

        return state

    except Exception as e:
        logger.error(f"Failed to load session {session_id}: {e}", exc_info=True)
        # On error, start fresh
        state["turn_count"] = 0
        state["is_active"] = True
        state["conversation_history"] = []
        state["user_context"] = state.get("user_context", {})
        state["clarification_state"] = create_empty_clarification_state()
        state["collected_findings"] = {}
        state["agent_plan"] = []
        return state


def save_session_node(state: SupervisorState) -> SupervisorState:
    """
    Save session to store

    This node is executed at the END of the orchestrator workflow (before returning to user).
    It persists conversation state for future turns.

    Persists:
    - user_context (updated with new information extracted from current turn)
    - conversation_history (appended current turn's query and response)
    - clarification_state (if waiting for user response)
    - turn_count (incremented)
    - agent_plan (if multi-step plan in progress)

    Args:
        state: SupervisorState after agent execution

    Returns:
        Same state (saving is side effect)

    Example:
        >>> state = {"session_id": "abc-123", "final_response": "Use Urea", ...}
        >>> state = save_session_node(state)
        >>> # State is now persisted to session store
    """
    session_id = state.get("session_id")

    if not session_id:
        logger.warning("No session_id provided - cannot save session")
        return state

    try:
        store = get_session_store()

        # Increment turn count
        state["turn_count"] = state.get("turn_count", 0) + 1

        # Save to store
        store.save(session_id, state)

        logger.info(
            f"Saved session {session_id} "
            f"(turn {state['turn_count']}, "
            f"active: {state.get('is_active', False)})"
        )

        return state

    except Exception as e:
        logger.error(f"Failed to save session {session_id}: {e}", exc_info=True)
        # Continue even if save fails (don't break user flow)
        return state


def reset_ephemeral_fields_node(state: SupervisorState) -> SupervisorState:
    """
    Reset fields that should not persist across turns

    This node is called by Supervisor after synthesis, before returning to user.
    It prevents state pollution between query cycles.

    Resets:
    - agent_plan (if completed)
    - next_agent (cleared after routing)
    - collected_findings (one-time results)
    - clarification_state (if resolved, otherwise keep for next turn)

    Keeps:
    - user_context (long-term memory)
    - conversation_history (for context)
    - session_id (for tracking)
    - turn_count (for statistics)

    Args:
        state: SupervisorState

    Returns:
        State with ephemeral fields reset

    Example:
        >>> state = {"agent_plan": ["crop_agent"], "next_agent": "fertilizer_agent", ...}
        >>> state = reset_ephemeral_fields_node(state)
        >>> state["agent_plan"]
        []
    """
    # Reset per-turn fields
    state["next_agent"] = None

    # Only reset collected_findings if not in active clarification
    if not state.get("is_active"):
        state["collected_findings"] = {}

    # Only reset agent_plan if completed
    if not state.get("agent_plan"):
        state["agent_plan"] = []

    # Only reset clarification_state if resolved (no pending clarifications)
    clarification_state = state.get("clarification_state", {})
    if not any(req is not None for req in clarification_state.values()):
        state["clarification_state"] = create_empty_clarification_state()

    logger.info("Ephemeral fields reset for next turn")

    return state


def get_session_info_helper(session_id: str) -> Dict[str, Any]:
    """
    Helper function to get session information for debugging/monitoring

    Args:
        session_id: Session identifier

    Returns:
        Dict with session metadata

    Example:
        >>> info = get_session_info_helper("abc-123")
        >>> info["turn_count"]
        5
    """
    try:
        store = get_session_store()
        return store.get_session_info(session_id)
    except Exception as e:
        logger.error(f"Failed to get session info for {session_id}: {e}")
        return {"error": str(e)}


def clear_session_helper(session_id: str) -> bool:
    """
    Helper function to manually clear a session (for debugging/testing)

    Args:
        session_id: Session identifier

    Returns:
        True if cleared, False otherwise

    Example:
        >>> cleared = clear_session_helper("abc-123")
        >>> cleared
        True
    """
    try:
        store = get_session_store()
        return store.delete(session_id)
    except Exception as e:
        logger.error(f"Failed to clear session {session_id}: {e}")
        return False
