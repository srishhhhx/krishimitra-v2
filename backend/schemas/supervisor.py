"""
Supervisor State Schemas for Multi-Turn Conversation Management

This module defines the state schemas for the Supervisor Agent, which manages
multi-turn conversations, clarifications, and user context/memory.

Key Principles:
- Supervisor owns ALL user interaction (only entity that talks)
- Agents declare missing info via state mutation
- Multi-turn conversations handled through clarification_state
- Memory managed across three tiers: short-term, medium-term, long-term
"""
from typing import TypedDict, List, Dict, Any, Optional, Literal
from datetime import datetime
from enum import Enum


# ============================================================================
# Enums for Resolution Strategies
# ============================================================================

class ResolutionStrategy(str, Enum):
    """
    How agents should handle clarification responses

    REPLACE: Replace existing value with new value
    APPEND: Append to existing list/array
    NORMALIZE: Normalize/standardize the value (e.g., "काली मिट्टी" → "black")
    VALIDATE_ONLY: Only validate, don't store (for confirmations)
    """
    REPLACE = "replace"
    APPEND = "append"
    NORMALIZE = "normalize"
    VALIDATE_ONLY = "validate_only"


# ============================================================================
# Conversation Turn Schema
# ============================================================================

class ConversationTurn(TypedDict):
    """
    Single turn in conversation history

    Represents one user message or one assistant response in the conversation.

    Example:
        {
            "role": "user",
            "content": "मुझे फसल की सिफारिश चाहिए",
            "timestamp": datetime(2025, 1, 15, 10, 30, 0),
            "metadata": {"language": "hi", "intent": "crop_recommendation"}
        }
    """
    role: Literal["user", "assistant", "system"]
    content: str
    timestamp: datetime
    metadata: Optional[Dict[str, Any]]  # e.g., {"agent": "crop_agent", "latency_ms": 450}


# ============================================================================
# User Context Schema (Long-Term Memory)
# ============================================================================

class UserContext(TypedDict, total=False):
    """
    User profile and accumulated context across conversation

    This is the LONG-TERM MEMORY that persists across sessions.
    Stored in MongoDB users collection.

    Example:
        {
            "user_id": "farmer123",
            "location": {"lat": 18.5, "lon": 73.8, "district": "Pune", "state": "Maharashtra"},
            "soil_type": "black",
            "crop_history": ["wheat", "rice", "sugarcane"],
            "farm_size_acres": 5.0,
            "preferred_language": "mr",
            "last_query_timestamp": datetime(...),
            "mentioned_crops": ["wheat", "cotton"],
            "mentioned_diseases": ["leaf_blight"],
            "inferred_preferences": {"irrigation": "drip", "fertilizer_type": "organic"}
        }
    """
    user_id: str  # Required

    # Farm profile
    location: Optional[Dict[str, Any]]  # {"lat": float, "lon": float, "district": str, "state": str}
    soil_type: Optional[str]  # "red", "black", "alluvial", "sandy", "clay"
    crop_history: List[str]  # ["wheat", "rice", "sugarcane"]
    farm_size_acres: Optional[float]
    preferred_language: str  # "en", "hi", "mr", "te", "bn", "ta"

    # Activity tracking
    last_query_timestamp: Optional[datetime]

    # Accumulated context from conversations
    mentioned_crops: List[str]  # Crops mentioned in queries
    mentioned_diseases: List[str]  # Diseases encountered
    inferred_preferences: Dict[str, Any]  # {"irrigation": "drip", "fertilizer_type": "organic"}

    # Session-specific temporary fields (not persisted long-term)
    temperature: Optional[float]  # From weather queries or user input
    humidity: Optional[float]
    rainfall: Optional[float]
    nitrogen: Optional[float]  # NPK values from soil tests
    phosphorus: Optional[float]
    potassium: Optional[float]
    ph: Optional[float]


# ============================================================================
# Clarification Request Schema (Core of Multi-Turn Logic)
# ============================================================================

class ClarificationRequest(TypedDict, total=False):
    """
    Standardized clarification request from an agent

    KEY PRINCIPLE: Agents NEVER talk to users. They only declare missing info.

    This schema captures:
    - What fields are missing
    - How to ask for them (metadata)
    - How to parse responses (resolution_strategy)
    - Loop prevention (retry_count, max_attempts)

    Example (Single Field):
        {
            "needs_clarification": True,
            "requested_fields": ["soil_type"],
            "missing_field_descriptions": {
                "soil_type": "Specify the soil type (red/black/alluvial/sandy/clay)"
            },
            "field_types": {"soil_type": "enum"},
            "allowed_values": {"soil_type": ["red", "black", "alluvial", "sandy", "clay"]},
            "resolution_strategy": {"soil_type": "normalize"},
            "agent_waiting": "crop_agent",
            "original_agent_input": {"temperature": 28, "humidity": 65},
            "partial_output": None,
            "question_for_user": "What is your soil type? Choose from: red, black, alluvial, sandy, or clay",
            "retry_count": 0,
            "max_attempts": 3
        }

    Example (Multiple Fields):
        {
            "needs_clarification": True,
            "requested_fields": ["soil_type", "farm_size"],
            "missing_field_descriptions": {
                "soil_type": "Your soil type (red/black/alluvial/sandy/clay)",
                "farm_size": "Your farm size in acres"
            },
            "field_types": {"soil_type": "enum", "farm_size": "float"},
            "allowed_values": {"soil_type": ["red", "black", "alluvial", "sandy", "clay"]},
            "resolution_strategy": {"soil_type": "normalize", "farm_size": "replace"},
            "agent_waiting": "crop_agent",
            "question_for_user": "To continue, I need:\n1. Your soil type (red/black/alluvial/sandy/clay)\n2. Your farm size in acres",
            "retry_count": 0,
            "max_attempts": 3
        }
    """
    # Status
    needs_clarification: bool  # True if agent is waiting for user input

    # Field requirements
    requested_fields: List[str]  # ["soil_type", "crop_name"]

    # Field metadata for intelligent question generation and parsing
    missing_field_descriptions: Dict[str, str]
    # Example: {"soil_type": "Specify soil type (red/black/...)", "crop_name": "Which crop?"}

    field_types: Dict[str, str]
    # Example: {"soil_type": "enum", "farm_size": "float", "crop_name": "string"}

    allowed_values: Dict[str, List[str]]
    # Example: {"soil_type": ["red", "black", "alluvial", "sandy", "clay"]}

    # **NEW: Resolution Strategy (per-field)**
    resolution_strategy: Dict[str, ResolutionStrategy]
    # Example: {"soil_type": "normalize", "crop_history": "append", "farm_size": "replace"}
    # - "normalize": Translate/standardize ("काली मिट्टी" → "black")
    # - "replace": Overwrite existing value
    # - "append": Add to list (for crop_history, etc.)
    # - "validate_only": Just confirm, don't store

    # Agent context
    agent_waiting: str  # "crop_agent", "fertilizer_agent", etc.
    original_agent_input: Dict[str, Any]  # What the agent received before pausing
    partial_output: Optional[Dict[str, Any]]  # If agent has partial results

    # User-facing question (generated by agent or supervisor)
    question_for_user: str
    # Example: "What is your soil type? Choose from: red, black, alluvial, sandy, or clay"

    # **NEW: Loop prevention**
    retry_count: int  # Increment on each retry (starts at 0)
    max_attempts: int  # Default: 3 (fallback after 3 failed attempts)


# ============================================================================
# Combined Clarification State (Multi-Agent Support)
# ============================================================================

class CombinedClarificationRequest(TypedDict):
    """
    Combined clarification request from multiple agents

    When multiple agents need clarification simultaneously, we combine them
    into a single question to avoid asking the user multiple times in a row.

    Example:
        Agent 1 (crop_agent) needs: soil_type
        Agent 2 (weather_agent) needs: location

        Combined:
        {
            "needs_clarification": True,
            "agents_waiting": ["crop_agent", "weather_agent"],
            "requested_fields": ["soil_type", "location"],
            "field_to_agent_mapping": {
                "soil_type": "crop_agent",
                "location": "weather_agent"
            },
            "missing_field_descriptions": {...},
            "field_types": {...},
            "allowed_values": {...},
            "resolution_strategy": {...},
            "question_for_user": "To help you, I need:\n1. Your soil type (red/black/alluvial/sandy/clay)\n2. Your location",
            "retry_count": 0,
            "max_attempts": 3
        }
    """
    needs_clarification: bool
    agents_waiting: List[str]  # ["crop_agent", "weather_agent"]
    requested_fields: List[str]  # All fields from all agents
    field_to_agent_mapping: Dict[str, str]  # {"soil_type": "crop_agent", "location": "weather_agent"}

    # Merged metadata
    missing_field_descriptions: Dict[str, str]
    field_types: Dict[str, str]
    allowed_values: Dict[str, List[str]]
    resolution_strategy: Dict[str, ResolutionStrategy]

    # Combined question
    question_for_user: str

    # Loop prevention
    retry_count: int
    max_attempts: int


# ============================================================================
# Supervisor State (Top-Level Session State)
# ============================================================================

class SupervisorState(TypedDict, total=False):
    """
    Top-level state managed by Supervisor Agent

    This is the SHORT-TERM MEMORY (session-scoped, stored in Redis with 30-min TTL)

    Lifecycle:
    1. Created on first user message (or loaded from Redis if session exists)
    2. Updated after every turn
    3. Saved to Redis after each turn
    4. On session timeout: Flushed to MongoDB, deleted from Redis

    Example:
        {
            "session_id": "uuid-1234",
            "user_context": {...},
            "conversation_history": [...],
            "clarification_state": {
                "crop_agent": {...},
                "fertilizer_agent": None,
                "weather_agent": None
            },
            "current_query": "मुझे फसल की सिफारिश चाहिए",
            "current_query_timestamp": datetime(...),
            "orchestrator_result": {...},
            "orchestrator_error": None,
            "session_start_time": datetime(...),
            "turn_count": 5,
            "is_active": True,
            "executed_agents": ["crop_agent", "fertilizer_agent"]
        }
    """
    # Session identification
    session_id: str  # UUID for this conversation session

    # User context (long-term memory)
    user_context: UserContext

    # Conversation history (short-term memory, last 10 turns = 20 messages)
    conversation_history: List[ConversationTurn]

    # Clarification tracking (per-agent to avoid collisions)
    # Example: {"crop_agent": {...}, "fertilizer_agent": None, "weather_agent": None}
    clarification_state: Dict[str, Optional[ClarificationRequest]]

    # Combined clarification (when multiple agents need input)
    combined_clarification: Optional[CombinedClarificationRequest]

    # Current query context
    current_query: str
    current_query_timestamp: datetime

    # Orchestrator delegation
    orchestrator_result: Optional[Dict[str, Any]]  # Result from orchestrator execution
    orchestrator_error: Optional[str]

    # Session management
    session_start_time: datetime
    turn_count: int
    is_active: bool  # False when session ends/expires

    # **NEW: Agent execution tracking (needed for loop prevention)**
    executed_agents: List[str]  # Agents that have run in this turn (prevents infinite loops)


# ============================================================================
# In-Memory Session Store Schema (Phase 1 Implementation)
# ============================================================================

class SessionStoreEntry(TypedDict):
    """
    Entry in the in-memory session store

    For Phase 1, we use a simple in-memory dict.
    Phase 2 will migrate to Redis + MongoDB.

    Example:
        {
            "session_id": "uuid-1234",
            "supervisor_state": {...},
            "created_at": datetime(...),
            "last_accessed": datetime(...),
            "expires_at": datetime(...),
        }
    """
    session_id: str
    supervisor_state: SupervisorState
    created_at: datetime
    last_accessed: datetime
    expires_at: datetime  # 30 minutes from last_accessed


# ============================================================================
# Helper Functions for State Creation
# ============================================================================

def create_empty_clarification_state() -> Dict[str, Optional[ClarificationRequest]]:
    """
    Create empty clarification state for all agents

    Returns:
        {
            "crop_agent": None,
            "fertilizer_agent": None,
            "disease_agent": None,
            "weather_agent": None,
            "general_rag_agent": None,
        }
    """
    return {
        "crop_agent": None,
        "fertilizer_agent": None,
        "disease_agent": None,
        "weather_agent": None,
        "general_rag_agent": None,
    }


def create_initial_user_context(user_id: str, preferred_language: str = "en") -> UserContext:
    """
    Create initial user context for a new user

    Args:
        user_id: Unique user identifier
        preferred_language: Default language ("en", "hi", "mr", etc.)

    Returns:
        UserContext with minimal fields populated
    """
    return {
        "user_id": user_id,
        "location": None,
        "soil_type": None,
        "crop_history": [],
        "farm_size_acres": None,
        "preferred_language": preferred_language,
        "last_query_timestamp": None,
        "mentioned_crops": [],
        "mentioned_diseases": [],
        "inferred_preferences": {},
    }


def create_initial_supervisor_state(
    session_id: str,
    user_id: str,
    preferred_language: str = "en",
) -> SupervisorState:
    """
    Create initial supervisor state for a new session

    Args:
        session_id: UUID for this session
        user_id: Unique user identifier
        preferred_language: User's preferred language

    Returns:
        SupervisorState with initial values

    Example:
        >>> state = create_initial_supervisor_state("uuid-1234", "farmer123", "hi")
        >>> state["session_id"]
        'uuid-1234'
        >>> state["turn_count"]
        0
    """
    now = datetime.utcnow()

    return {
        "session_id": session_id,
        "user_context": create_initial_user_context(user_id, preferred_language),
        "conversation_history": [],
        "clarification_state": create_empty_clarification_state(),
        "combined_clarification": None,
        "current_query": "",
        "current_query_timestamp": now,
        "orchestrator_result": None,
        "orchestrator_error": None,
        "session_start_time": now,
        "turn_count": 0,
        "is_active": True,
    }


# ============================================================================
# Example Clarification Requests (for Testing)
# ============================================================================

def create_example_clarification_request(
    agent_name: str = "crop_agent",
    missing_fields: List[str] = None,
) -> ClarificationRequest:
    """
    Create an example clarification request for testing

    Args:
        agent_name: Name of the agent requesting clarification
        missing_fields: List of missing field names (default: ["soil_type"])

    Returns:
        ClarificationRequest with example values
    """
    if missing_fields is None:
        missing_fields = ["soil_type"]

    # Default metadata for common fields
    field_metadata = {
        "soil_type": {
            "description": "Your soil type (red/black/alluvial/sandy/clay)",
            "type": "enum",
            "allowed_values": ["red", "black", "alluvial", "sandy", "clay"],
            "resolution_strategy": ResolutionStrategy.NORMALIZE,
        },
        "crop_name": {
            "description": "Which crop are you asking about?",
            "type": "string",
            "allowed_values": [],
            "resolution_strategy": ResolutionStrategy.REPLACE,
        },
        "farm_size": {
            "description": "Your farm size in acres",
            "type": "float",
            "allowed_values": [],
            "resolution_strategy": ResolutionStrategy.REPLACE,
        },
        "location": {
            "description": "Your location (city or district)",
            "type": "string",
            "allowed_values": [],
            "resolution_strategy": ResolutionStrategy.NORMALIZE,
        },
    }

    # Build clarification request
    missing_field_descriptions = {}
    field_types = {}
    allowed_values = {}
    resolution_strategy = {}

    for field in missing_fields:
        metadata = field_metadata.get(field, {
            "description": f"Please provide {field}",
            "type": "string",
            "allowed_values": [],
            "resolution_strategy": ResolutionStrategy.REPLACE,
        })

        missing_field_descriptions[field] = metadata["description"]
        field_types[field] = metadata["type"]
        if metadata["allowed_values"]:
            allowed_values[field] = metadata["allowed_values"]
        resolution_strategy[field] = metadata["resolution_strategy"]

    # Generate question
    if len(missing_fields) == 1:
        field = missing_fields[0]
        question = missing_field_descriptions[field]
        if field in allowed_values:
            question += f". Choose from: {', '.join(allowed_values[field])}"
    else:
        question = "To continue, I need:\n"
        for i, field in enumerate(missing_fields, 1):
            question += f"{i}. {missing_field_descriptions[field]}\n"

    return {
        "needs_clarification": True,
        "requested_fields": missing_fields,
        "missing_field_descriptions": missing_field_descriptions,
        "field_types": field_types,
        "allowed_values": allowed_values,
        "resolution_strategy": resolution_strategy,
        "agent_waiting": agent_name,
        "original_agent_input": {},
        "partial_output": None,
        "question_for_user": question.strip(),
        "retry_count": 0,
        "max_attempts": 3,
    }
