"""
Pydantic schemas and TypedDict definitions for Agent System

This module defines the core state schemas and response models for the
multi-agent orchestration system in Krishi Mitra.

Updated for multi-turn conversation support with clarification handling.
"""
from typing import TypedDict, List, Dict, Any, Optional
from enum import Enum
from pydantic import BaseModel, Field

# Import clarification types from supervisor module
try:
    from schemas.supervisor import ClarificationRequest, ConversationTurn, UserContext
except ImportError:
    # Fallback for when supervisor.py doesn't exist yet
    ClarificationRequest = Dict[str, Any]  # type: ignore
    ConversationTurn = Dict[str, Any]  # type: ignore
    UserContext = Dict[str, Any]  # type: ignore


class AgentIntent(str, Enum):
    """
    Classification of user query intent for agent routing

    This enum defines the types of queries that the system can handle,
    each mapping to a specialized agent or service.
    """
    GENERAL_RAG = "general_rag"
    CROP_RECOMMENDATION = "crop_recommendation"
    FERTILIZER_ADVICE = "fertilizer_advice"
    DISEASE_DETECTION = "disease_detection"
    WEATHER_QUERY = "weather_query"


class AgentState(TypedDict, total=False):
    """
    State object for multi-agent orchestration workflow

    This TypedDict defines the shared state that flows through the
    LangGraph orchestrator. Each node can read and update specific fields.

    **Multi-Turn Conversation Support:**
    - Agents can request clarification by setting clarification_state[agent_name]
    - Supervisor handles all user communication
    - Agents NEVER talk to users directly

    Fields:
        Input Fields:
            user_query (str): The original user question
            user_context (Optional[UserContext]): User profile and accumulated context
            conversation_history (Optional[List[ConversationTurn]]): Recent conversation (last 3-6 turns)
            images (Optional[List[str]]): Base64 encoded images for disease detection

        Classification Fields:
            intent (Optional[str]): Classified intent (from AgentIntent enum)
            confidence (Optional[float]): Classification confidence score (0.0-1.0)
            classification_method (Optional[str]): Method used (keyword/llm)

        Agent Output Fields:
            rag_output (Optional[Dict[str, Any]]): Output from RAG agent
            crop_output (Optional[Dict[str, Any]]): Output from crop recommendation agent
            fertilizer_output (Optional[Dict[str, Any]]): Output from fertilizer agent
            disease_output (Optional[Dict[str, Any]]): Output from disease detection agent
            weather_output (Optional[Dict[str, Any]]): Output from weather agent

        **NEW: Clarification Fields:**
            clarification_state (Dict[str, Optional[ClarificationRequest]]): Per-agent clarification requests
                Example: {"crop_agent": {...}, "fertilizer_agent": None}
                - Agents set this when they need missing info
                - Supervisor reads this and asks user
                - Keys are agent names to avoid collisions

        **NEW: Supervisor V2 Pattern Fields:**
            agent_plan (Optional[List[str]]): Ordered list of agents to execute
                Example: ["crop_agent", "fertilizer_agent"]
                - Set by Supervisor during query classification
                - Supervisor pops from this list to determine next_agent
            next_agent (Optional[str]): Next agent to route to
                Example: "fertilizer_agent"
                - Set by Supervisor after planning or clarification
                - Read by conditional routing function
            final_response (Optional[str]): Final synthesized response from Supervisor
                - Set by Supervisor after all agents complete
                - Replaces individual agent outputs with unified response
            collected_findings (Optional[Dict[str, Any]]): Aggregated agent outputs (V2 pattern)
                Example: {"crop_agent": {"status": "success", "data": {...}}, "fertilizer_agent": {"status": "error", "error": "..."}}
                - Each specialist agent writes to this dict
                - Supervisor reads from this to synthesize final_response

        **NEW: Session Management Fields:**
            session_id (Optional[str]): Unique session identifier
                - Generated in load_session_node for new sessions
                - Used to save/load conversation state across turns
            turn_count (Optional[int]): Current turn number in session
                - Incremented on each new user message
                - Tracked for session analytics and cleanup
            is_active (Optional[bool]): Session activity status
                - True if session is ongoing
                - False if session has ended (greeting, thanks, error)

        Final Response Fields:
            answer (Optional[str]): Final synthesized answer for user (legacy, use final_response)
            metadata (Optional[Dict[str, Any]]): Additional response metadata
            sources (Optional[List[Dict[str, Any]]]): Source documents/references

        Execution Tracking:
            latencies (Optional[Dict[str, float]]): Node-level execution times (ms)
            total_latency_ms (Optional[float]): Total orchestration time
            executed_agents (Optional[List[str]]): List of agents that ran

        Error Handling:
            error (Optional[str]): Error message if any step failed
            fallback_used (Optional[bool]): Whether fallback logic was triggered
    """
    # Input fields
    user_query: str
    user_context: Optional[UserContext]  # Updated to use UserContext type
    conversation_history: Optional[List[ConversationTurn]]  # NEW: For context-aware agents
    images: Optional[List[str]]

    # Classification fields
    intent: Optional[str]
    confidence: Optional[float]
    classification_method: Optional[str]

    # Agent output fields (unchanged for backward compatibility)
    rag_output: Optional[Dict[str, Any]]
    crop_output: Optional[Dict[str, Any]]
    fertilizer_output: Optional[Dict[str, Any]]
    disease_output: Optional[Dict[str, Any]]
    weather_output: Optional[Dict[str, Any]]

    # NEW: Clarification handling (key addition for multi-turn support)
    clarification_state: Optional[Dict[str, Optional[ClarificationRequest]]]
    # Example: {"crop_agent": {...}, "fertilizer_agent": None, "weather_agent": None}

    # **NEW: Supervisor V2 Pattern Fields**
    agent_plan: Optional[List[str]]  # Planned agent execution order (e.g., ["crop_agent", "fertilizer_agent"])
    next_agent: Optional[str]  # Next agent to route to (set by supervisor)
    final_response: Optional[str]  # Final synthesized response from supervisor
    collected_findings: Optional[Dict[str, Any]]  # V2 pattern: {"agent_name": {"status": "success", "data": {...}}}

    # **NEW: Session Management Fields**
    session_id: Optional[str]  # Unique session identifier for multi-turn conversations
    turn_count: Optional[int]  # Current turn number in the conversation
    is_active: Optional[bool]  # Whether the session is still active

    # Final response fields
    answer: Optional[str]
    metadata: Optional[Dict[str, Any]]
    sources: Optional[List[Dict[str, Any]]]

    # Execution tracking
    latencies: Optional[Dict[str, float]]
    total_latency_ms: Optional[float]
    executed_agents: Optional[List[str]]

    # Error handling
    error: Optional[str]
    fallback_used: Optional[bool]


# ============================================================================
# Pydantic Response Models for API Endpoints
# ============================================================================

class AgentResponse(BaseModel):
    """
    Base response model for agent execution results

    Example:
        {
            "answer": "For wheat cultivation in Punjab, sow between November 1-15...",
            "sources": [{"source": "wheat_guide.pdf", "page": 12}],
            "confidence": 0.92,
            "latency_ms": 1250,
            "agent_type": "crop_recommendation"
        }
    """
    answer: str = Field(..., description="Generated answer or recommendation")
    sources: Optional[List[Dict[str, Any]]] = Field(
        default=None,
        description="Source references for the answer"
    )
    confidence: Optional[float] = Field(
        default=None,
        description="Confidence score for the response (0.0-1.0)",
        ge=0.0,
        le=1.0
    )
    latency_ms: int = Field(..., description="Total response time in milliseconds", ge=0)
    agent_type: Optional[str] = Field(
        default=None,
        description="Type of agent that handled the query"
    )
    metadata: Optional[Dict[str, Any]] = Field(
        default=None,
        description="Additional metadata about the response"
    )


class CropPrediction(BaseModel):
    """
    Response model for crop recommendation agent

    Example:
        {
            "crop": "Rice",
            "confidence": 0.89,
            "reasoning": "Based on soil pH 6.5, rainfall 200mm, temperature 28°C...",
            "alternative_crops": ["Wheat", "Maize"],
            "soil_parameters": {...},
            "climate_parameters": {...}
        }
    """
    crop: str = Field(..., description="Recommended crop name")
    confidence: float = Field(
        ...,
        description="Prediction confidence (0.0-1.0)",
        ge=0.0,
        le=1.0
    )
    reasoning: str = Field(..., description="Explanation for the recommendation")
    alternative_crops: Optional[List[str]] = Field(
        default=None,
        description="Other suitable crops"
    )
    soil_parameters: Optional[Dict[str, float]] = Field(
        default=None,
        description="Soil parameters used (N, P, K, pH, etc.)"
    )
    climate_parameters: Optional[Dict[str, float]] = Field(
        default=None,
        description="Climate parameters used (temperature, rainfall, humidity)"
    )


class FertilizerRecommendation(BaseModel):
    """
    Response model for fertilizer recommendation agent

    Example:
        {
            "fertilizer": "Urea",
            "quantity_kg_per_acre": 50,
            "schedule": [
                {"stage": "Basal", "days_after_sowing": 0, "amount_kg": 20},
                {"stage": "First_Top", "days_after_sowing": 30, "amount_kg": 30}
            ],
            "reasoning": "For wheat crop in sandy loam soil with low nitrogen...",
            "npk_ratio": "46-0-0"
        }
    """
    fertilizer: str = Field(..., description="Recommended fertilizer name")
    quantity_kg_per_acre: Optional[float] = Field(
        default=None,
        description="Total fertilizer quantity in kg per acre",
        ge=0
    )
    schedule: Optional[List[Dict[str, Any]]] = Field(
        default=None,
        description="Application schedule with stages and amounts"
    )
    reasoning: str = Field(..., description="Explanation for the recommendation")
    npk_ratio: Optional[str] = Field(
        default=None,
        description="NPK ratio of recommended fertilizer (e.g., '20-20-20')"
    )
    soil_parameters: Optional[Dict[str, float]] = Field(
        default=None,
        description="Soil parameters considered"
    )
    crop: Optional[str] = Field(default=None, description="Crop for which fertilizer is recommended")


class DiseaseAnalysis(BaseModel):
    """
    Response model for disease detection agent

    Example:
        {
            "crop": "Tomato",
            "disease": "Late Blight",
            "confidence": 0.87,
            "severity": "moderate",
            "treatment": "Apply copper-based fungicide every 7 days...",
            "preventive_measures": ["Ensure proper spacing", "Avoid overhead irrigation"],
            "detection_method": "cnn_image_classification"
        }
    """
    crop: str = Field(..., description="Detected crop type")
    disease: str = Field(..., description="Detected disease name")
    confidence: float = Field(
        ...,
        description="Detection confidence (0.0-1.0)",
        ge=0.0,
        le=1.0
    )
    severity: Optional[str] = Field(
        default=None,
        description="Disease severity level (mild/moderate/severe)"
    )
    treatment: str = Field(..., description="Recommended treatment measures")
    preventive_measures: Optional[List[str]] = Field(
        default=None,
        description="Preventive measures to avoid recurrence"
    )
    detection_method: Optional[str] = Field(
        default=None,
        description="Method used for detection (e.g., 'cnn_image_classification')"
    )
    symptoms: Optional[List[str]] = Field(
        default=None,
        description="Observed or described symptoms"
    )


class WeatherInfo(BaseModel):
    """
    Response model for weather query agent

    Example:
        {
            "location": "Ludhiana, Punjab",
            "current_temp_celsius": 32.5,
            "condition": "Partly Cloudy",
            "rainfall_mm": 0,
            "humidity_percent": 65,
            "forecast_days": 7,
            "agricultural_advisory": "Suitable conditions for irrigation...",
            "timestamp": "2025-11-09T10:30:00Z"
        }
    """
    location: str = Field(..., description="Location for which weather is provided")
    current_temp_celsius: float = Field(..., description="Current temperature in Celsius")
    condition: str = Field(..., description="Weather condition description")
    rainfall_mm: Optional[float] = Field(
        default=None,
        description="Rainfall in millimeters",
        ge=0
    )
    humidity_percent: Optional[float] = Field(
        default=None,
        description="Humidity percentage",
        ge=0,
        le=100
    )
    forecast_days: Optional[int] = Field(
        default=None,
        description="Number of forecast days included",
        ge=0
    )
    agricultural_advisory: Optional[str] = Field(
        default=None,
        description="Agricultural advisory based on weather"
    )
    timestamp: str = Field(..., description="Timestamp of weather data (ISO 8601)")


class ClassificationResult(BaseModel):
    """
    Response model for query classification

    Example:
        {
            "intent": "crop_recommendation",
            "confidence": 0.95,
            "method": "keyword",
            "latency_ms": 45,
            "alternative_intents": [
                {"intent": "general_rag", "confidence": 0.15}
            ]
        }
    """
    intent: str = Field(..., description="Classified intent (AgentIntent enum value)")
    confidence: float = Field(
        ...,
        description="Classification confidence (0.0-1.0)",
        ge=0.0,
        le=1.0
    )
    method: str = Field(
        ...,
        description="Classification method used (keyword/llm)"
    )
    latency_ms: float = Field(..., description="Classification time in milliseconds", ge=0)
    alternative_intents: Optional[List[Dict[str, Any]]] = Field(
        default=None,
        description="Alternative intents with their confidence scores"
    )


class OrchestratorResponse(BaseModel):
    """
    Complete response from the orchestrator

    This is the final response returned by the orchestrator after
    routing to appropriate agents and synthesizing results.

    Example:
        {
            "answer": "Based on your soil conditions, I recommend planting Rice...",
            "intent": "crop_recommendation",
            "confidence": 0.92,
            "sources": [...],
            "executed_agents": ["classifier", "crop_agent"],
            "total_latency_ms": 1850,
            "node_latencies": {
                "classify": 45,
                "crop_agent": 1200,
                "synthesize": 50
            }
        }
    """
    answer: str = Field(..., description="Final synthesized answer")
    intent: str = Field(..., description="Classified query intent")
    confidence: Optional[float] = Field(
        default=None,
        description="Overall confidence in the response",
        ge=0.0,
        le=1.0
    )
    sources: Optional[List[Dict[str, Any]]] = Field(
        default=None,
        description="Sources used for the answer"
    )
    executed_agents: List[str] = Field(
        ...,
        description="List of agents that were executed"
    )
    total_latency_ms: int = Field(..., description="Total orchestration time", ge=0)
    node_latencies: Dict[str, float] = Field(
        ...,
        description="Per-node execution latencies"
    )
    metadata: Optional[Dict[str, Any]] = Field(
        default=None,
        description="Additional response metadata"
    )
    error: Optional[str] = Field(default=None, description="Error message if any")
    fallback_used: Optional[bool] = Field(
        default=False,
        description="Whether fallback logic was used"
    )


# ============================================================================
# Example State Instances for Testing
# ============================================================================

def create_example_state(
    query: str = "What crop should I plant?",
    intent: Optional[str] = None,
    user_id: str = "test_user"
) -> AgentState:
    """
    Create an example AgentState for testing

    Args:
        query: User query string
        intent: Optional pre-classified intent
        user_id: User identifier (default: "test_user")

    Returns:
        AgentState instance with basic fields populated

    Example:
        >>> state = create_example_state("What crop should I plant?", "crop_recommendation")
        >>> state["user_query"]
        'What crop should I plant?'
        >>> state["clarification_state"]
        {'crop_agent': None, 'fertilizer_agent': None, ...}
    """
    # Import here to avoid circular dependency
    from schemas.supervisor import create_initial_user_context, create_empty_clarification_state

    state: AgentState = {
        "user_query": query,
        "user_context": create_initial_user_context(user_id, "en"),
        "conversation_history": [],
        "images": None,
        "intent": intent,
        "confidence": None,
        "classification_method": None,
        "rag_output": None,
        "crop_output": None,
        "fertilizer_output": None,
        "disease_output": None,
        "weather_output": None,
        "clarification_state": create_empty_clarification_state(),
        "answer": None,
        "metadata": None,
        "sources": None,
        "latencies": {},
        "total_latency_ms": None,
        "executed_agents": [],
        "error": None,
        "fallback_used": False
    }
    return state
