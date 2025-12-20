"""
Base Agent Classes for Krishi Mitra Multi-Agent System

This module provides the abstract base classes and concrete implementations
for different types of agents in the orchestration system.

Updated with multi-turn conversation and clarification support:
- Agents declare missing info via _check_required_fields()
- Agents NEVER talk to users directly
- Supervisor handles all clarification
"""
import time
from abc import ABC, abstractmethod
from typing import Dict, Any, List, Optional
from functools import wraps

from schemas.agents import AgentState
from schemas.supervisor import ClarificationRequest, ResolutionStrategy
from core.logging import get_logger

logger = get_logger(__name__)


def track_latency(node_name: Optional[str] = None):
    """
    Decorator to track execution latency of agent methods

    Args:
        node_name: Optional node name for logging. If not provided,
                   uses the function name.

    Example:
        @track_latency("my_agent_node")
        async def run(self, state: AgentState) -> AgentState:
            # ... agent logic ...
            return state
    """
    def decorator(func):
        @wraps(func)
        async def async_wrapper(*args, **kwargs):
            start_time = time.perf_counter()
            result = await func(*args, **kwargs)
            latency_ms = (time.perf_counter() - start_time) * 1000

            # If result is AgentState, add latency to state
            if isinstance(result, dict) and "latencies" in result:
                name = node_name or func.__name__
                if result.get("latencies") is None:
                    result["latencies"] = {}
                result["latencies"][name] = latency_ms

                logger.log_node_execution(
                    node_name=name,
                    latency_ms=latency_ms,
                    metadata={"agent": args[0].name if args else "unknown"}
                )

            return result

        @wraps(func)
        def sync_wrapper(*args, **kwargs):
            start_time = time.perf_counter()
            result = func(*args, **kwargs)
            latency_ms = (time.perf_counter() - start_time) * 1000

            # If result is AgentState, add latency to state
            if isinstance(result, dict) and "latencies" in result:
                name = node_name or func.__name__
                if result.get("latencies") is None:
                    result["latencies"] = {}
                result["latencies"][name] = latency_ms

                logger.log_node_execution(
                    node_name=name,
                    latency_ms=latency_ms,
                    metadata={"agent": args[0].name if args else "unknown"}
                )

            return result

        # Return appropriate wrapper based on whether func is async
        import inspect
        if inspect.iscoroutinefunction(func):
            return async_wrapper
        else:
            return sync_wrapper

    return decorator


class BaseAgent(ABC):
    """
    Abstract base class for all agents in the system

    **Multi-Turn Conversation Support:**
    - Agents declare missing info via _check_required_fields()
    - Agents NEVER talk to users directly
    - Supervisor handles all clarification

    All agents must implement the `run` method which takes an AgentState
    and returns an updated AgentState. Agents should be stateless and
    side-effect-free except for logging.

    Attributes:
        name (str): Unique identifier for the agent
        description (str): Human-readable description of agent's purpose
    """

    def __init__(self, name: str, description: str):
        """
        Initialize base agent

        Args:
            name: Unique name for this agent (e.g., "crop_agent")
            description: Description of agent's capabilities
        """
        self.name = name
        self.description = description
        logger.info(f"Initialized {self.__class__.__name__}: {name}")

    # ========================================================================
    # Clarification Handling (New Multi-Turn Support)
    # ========================================================================

    def _check_required_fields(
        self,
        input_data: Dict[str, Any],
        required_fields: List[str],
        field_metadata: Dict[str, Dict[str, Any]],
    ) -> Optional[ClarificationRequest]:
        """
        Check for missing required fields and generate clarification request

        KEY PRINCIPLE: Agents NEVER talk to users. They only declare missing info.

        This method:
        1. Checks which required fields are missing from input_data
        2. If missing, generates a ClarificationRequest
        3. Returns None if all fields present

        Args:
            input_data: Input provided to agent (from state["user_context"] or state)
            required_fields: List of field names that MUST be present
            field_metadata: Metadata for each field:
                {
                    "field_name": {
                        "type": "enum" | "string" | "float" | "int" | "bool",
                        "description": "User-facing description",
                        "allowed_values": ["val1", "val2"],  # For enums
                        "resolution_strategy": ResolutionStrategy.NORMALIZE,  # How to handle response
                        "examples": ["example1", "example2"]  # Optional examples
                    }
                }

        Returns:
            ClarificationRequest if fields missing, None otherwise

        Example:
            >>> metadata = {
            ...     "soil_type": {
            ...         "type": "enum",
            ...         "description": "Your soil type (red/black/alluvial/sandy/clay)",
            ...         "allowed_values": ["red", "black", "alluvial", "sandy", "clay"],
            ...         "resolution_strategy": ResolutionStrategy.NORMALIZE
            ...     }
            ... }
            >>> req = agent._check_required_fields(
            ...     input_data={"temperature": 28},
            ...     required_fields=["soil_type", "temperature"],
            ...     field_metadata=metadata
            ... )
            >>> req["requested_fields"]
            ['soil_type']
        """
        missing_fields = []

        # Check which required fields are missing
        for field in required_fields:
            if field not in input_data or input_data[field] is None:
                missing_fields.append(field)

        # All fields present - no clarification needed
        if not missing_fields:
            return None

        # Build clarification request
        missing_field_descriptions = {}
        field_types = {}
        allowed_values = {}
        resolution_strategy = {}

        for field in missing_fields:
            metadata = field_metadata.get(field, {})

            # Description (required)
            description = metadata.get("description", f"Please provide {field}")
            missing_field_descriptions[field] = description

            # Type (default: string)
            field_type = metadata.get("type", "string")
            field_types[field] = field_type

            # Allowed values (for enums)
            if "allowed_values" in metadata and metadata["allowed_values"]:
                allowed_values[field] = metadata["allowed_values"]

            # Resolution strategy (default: replace)
            strategy = metadata.get("resolution_strategy", ResolutionStrategy.REPLACE)
            resolution_strategy[field] = strategy

        # Generate user-facing question
        question = self._generate_clarification_question(
            missing_fields=missing_fields,
            missing_field_descriptions=missing_field_descriptions,
            allowed_values=allowed_values
        )

        # Create clarification request
        clarification_request: ClarificationRequest = {
            "needs_clarification": True,
            "requested_fields": missing_fields,
            "missing_field_descriptions": missing_field_descriptions,
            "field_types": field_types,
            "allowed_values": allowed_values,
            "resolution_strategy": resolution_strategy,
            "agent_waiting": self.name,
            "original_agent_input": input_data,
            "partial_output": None,
            "question_for_user": question,
            "retry_count": 0,
            "max_attempts": 3,
        }

        logger.info(
            f"{self.name}: Missing required fields: {missing_fields}. "
            f"Requesting clarification."
        )

        return clarification_request

    def _generate_clarification_question(
        self,
        missing_fields: List[str],
        missing_field_descriptions: Dict[str, str],
        allowed_values: Dict[str, List[str]],
    ) -> str:
        """
        Generate user-facing clarification question

        Generates a natural, concise question asking for missing fields.

        Args:
            missing_fields: List of missing field names
            missing_field_descriptions: Field descriptions
            allowed_values: Allowed values for enum fields

        Returns:
            User-facing question string

        Example:
            Single field:
            "What is your soil type? Choose from: red, black, alluvial, sandy, clay"

            Multiple fields:
            "To continue, I need:
            1. Your soil type (red/black/alluvial/sandy/clay)
            2. Your farm size in acres"
        """
        if len(missing_fields) == 1:
            field = missing_fields[0]
            question = missing_field_descriptions[field]

            # Add options for enum fields
            if field in allowed_values and allowed_values[field]:
                options = ", ".join(allowed_values[field])
                question += f". Choose from: {options}"

            return question

        else:
            # Multiple fields - numbered list
            question = "To continue, I need:\n"
            for i, field in enumerate(missing_fields, 1):
                description = missing_field_descriptions[field]

                # Add options inline for enums
                if field in allowed_values and allowed_values[field]:
                    options = "/".join(allowed_values[field])
                    description += f" ({options})"

                question += f"{i}. {description}\n"

            return question.strip()

    def _extract_input_from_state(
        self,
        state: AgentState,
        field_names: List[str]
    ) -> Dict[str, Any]:
        """
        Extract input fields from state

        Checks (in order of priority):
        1. state["user_context"] first (preferred - explicitly provided by user)
        2. state["collected_findings"] from previous agents (inter-agent sharing)
        3. state directly as fallback

        BUG FIX #2: Now checks collected_findings from previous agents to enable
        inter-agent state sharing (e.g., fertilizer_agent uses crop from crop_agent)

        Args:
            state: Current agent state
            field_names: List of field names to extract

        Returns:
            Dict with extracted field values (None if not found)

        Example:
            >>> state = {
            ...     "user_context": {"soil_type": "black"},
            ...     "collected_findings": {
            ...         "crop_agent": {"status": "success", "data": {"recommended_crop": "wheat"}}
            ...     }
            ... }
            >>> agent._extract_input_from_state(state, ["soil_type", "crop_type", "temperature"])
            {'soil_type': 'black', 'crop_type': 'wheat', 'temperature': None}
        """
        input_data = {}

        for field in field_names:
            # Priority 1: Check user_context first (user-provided values)
            if state.get("user_context") and field in state["user_context"]:
                input_data[field] = state["user_context"][field]
                continue

            # Priority 2: Check collected_findings from previous agents (NEW - Bug #2 fix)
            if state.get("collected_findings"):
                value_from_findings = self._extract_from_collected_findings(
                    state["collected_findings"],
                    field
                )
                if value_from_findings is not None:
                    input_data[field] = value_from_findings
                    logger.info(f"{self.name}: Using {field}={value_from_findings} from previous agent findings")
                    continue

            # Priority 3: Check state directly
            if field in state:
                input_data[field] = state[field]
            else:
                input_data[field] = None

        return input_data

    def _extract_from_collected_findings(
        self,
        collected_findings: Dict[str, Any],
        field_name: str
    ) -> Optional[Any]:
        """
        Extract field value from collected_findings of previous agents

        This enables inter-agent state sharing. For example:
        - crop_agent outputs "recommended_crop" → fertilizer_agent reads as "crop_type"
        - weather_agent outputs "temperature" → crop_agent reads as "temperature"

        Args:
            collected_findings: Dict of {agent_name: {status, data}} from previous agents
            field_name: Field to extract (e.g., "crop_type", "temperature")

        Returns:
            Field value if found in any agent's findings, None otherwise
        """
        # Field mapping: which agent provides which fields
        field_to_agent_mapping = {
            # Crop-related fields (from crop_agent)
            "crop_type": ("crop_agent", "recommended_crop"),
            "crop": ("crop_agent", "recommended_crop"),
            "recommended_crop": ("crop_agent", "recommended_crop"),

            # Weather-related fields (from weather_agent)
            "location": ("weather_agent", "location"),
            "temperature": ("weather_agent", "temperature"),
            "humidity": ("weather_agent", "humidity"),
            "wind_speed": ("weather_agent", "wind_speed"),

            # Fertilizer-related fields (from fertilizer_agent)
            "fertilizer_name": ("fertilizer_agent", "fertilizer_name"),
            "fertilizer_type": ("fertilizer_agent", "fertilizer_name"),
            "npk_ratio": ("fertilizer_agent", "npk_ratio"),

            # Disease detection fields (from disease_detection_agent)
            "disease_name": ("disease_detection_agent", "disease_name"),
            "disease_detected": ("disease_detection_agent", "disease_name"),
            "is_healthy": ("disease_detection_agent", "is_healthy"),
        }

        # Check if we have a mapping for this field
        if field_name not in field_to_agent_mapping:
            return None

        agent_name, data_key = field_to_agent_mapping[field_name]

        # Check if that agent has executed and has data
        if agent_name not in collected_findings:
            return None

        agent_finding = collected_findings[agent_name]

        # Only extract from successful agent runs
        if agent_finding.get("status") != "success":
            return None

        data = agent_finding.get("data", {})
        return data.get(data_key)


    # ========================================================================
    # Abstract Methods (Must be implemented by subclasses)
    # ========================================================================

    @abstractmethod
    async def run(self, state: AgentState) -> AgentState:
        """
        Execute agent logic and update state

        This is the main entry point for agent execution. Agents should:
        1. Read necessary fields from state
        2. Perform their specialized task
        3. Update state with results
        4. Return the updated state

        Agents should NOT raise exceptions; instead, they should:
        - Catch all exceptions
        - Log errors
        - Set state["error"] field
        - Return state with error information

        Args:
            state: Current agent state

        Returns:
            Updated agent state with results or errors
        """
        pass

    def health_check(self) -> Dict[str, Any]:
        """
        Perform health check on the agent

        Returns:
            Health status dictionary with keys:
                - status: "healthy" | "degraded" | "unhealthy"
                - name: Agent name
                - description: Agent description
                - details: Optional additional details
        """
        return {
            "status": "healthy",
            "name": self.name,
            "description": self.description,
            "details": None
        }

    def __repr__(self) -> str:
        return f"{self.__class__.__name__}(name='{self.name}')"


class RAGAgent(BaseAgent):
    """
    Base class for agents that use Retrieval-Augmented Generation

    RAG agents typically follow this pattern:
    1. Embed the query
    2. Retrieve relevant chunks from vector DB
    3. Generate answer using LLM with retrieved context

    This class provides common utilities for RAG-based agents.
    """

    def __init__(
        self,
        name: str,
        description: str,
        embedding_service=None,
        retrieval_service=None,
        generation_service=None
    ):
        """
        Initialize RAG agent with required services

        Args:
            name: Agent name
            description: Agent description
            embedding_service: Service for text embeddings
            retrieval_service: Service for vector search
            generation_service: Service for LLM generation
        """
        super().__init__(name, description)
        self.embedding_service = embedding_service
        self.retrieval_service = retrieval_service
        self.generation_service = generation_service

    async def embed_query(self, query: str) -> tuple[List[float], float]:
        """
        Convert query to embedding vector

        Args:
            query: Text query

        Returns:
            Tuple of (embedding_vector, latency_ms)

        Raises:
            Exception: If embedding fails
        """
        if not self.embedding_service:
            raise ValueError(f"{self.name}: No embedding service configured")

        return self.embedding_service.embed_query(query)

    async def retrieve_chunks(
        self,
        query_embedding: List[float],
        top_k: int = 5,
        filters: Optional[Dict[str, Any]] = None
    ) -> tuple[Dict[str, Any], float]:
        """
        Retrieve relevant chunks from vector database

        Args:
            query_embedding: Query vector
            top_k: Number of chunks to retrieve
            filters: Optional metadata filters

        Returns:
            Tuple of (retrieval_results, latency_ms)

        Raises:
            Exception: If retrieval fails
        """
        if not self.retrieval_service:
            raise ValueError(f"{self.name}: No retrieval service configured")

        return self.retrieval_service.retrieve_chunks(
            query_embedding=query_embedding,
            top_k=top_k,
            filter_dict=filters
        )

    async def generate_answer(
        self,
        query: str,
        retrieved_chunks: List[Dict[str, Any]],
        max_tokens: Optional[int] = None,
        temperature: Optional[float] = None
    ) -> tuple[str, float]:
        """
        Generate answer using LLM with retrieved context

        Args:
            query: User's question
            retrieved_chunks: Retrieved document chunks
            max_tokens: Max tokens for generation
            temperature: LLM temperature

        Returns:
            Tuple of (generated_answer, latency_ms)

        Raises:
            Exception: If generation fails
        """
        if not self.generation_service:
            raise ValueError(f"{self.name}: No generation service configured")

        return self.generation_service.generate_answer(
            query=query,
            retrieved_chunks=retrieved_chunks,
            max_tokens=max_tokens,
            temperature=temperature
        )

    @abstractmethod
    async def run(self, state: AgentState) -> AgentState:
        """Execute RAG agent logic"""
        pass

    def health_check(self) -> Dict[str, Any]:
        """
        Check health of RAG agent and its dependencies

        Returns:
            Health status with service availability
        """
        status = super().health_check()
        status["services"] = {
            "embedding": self.embedding_service is not None,
            "retrieval": self.retrieval_service is not None,
            "generation": self.generation_service is not None
        }

        # Overall health is healthy only if all services are available
        all_services_available = all(status["services"].values())
        status["status"] = "healthy" if all_services_available else "degraded"

        return status


class ToolAgent(BaseAgent):
    """
    Base class for agents that wrap external tools or ML models

    Tool agents execute specific tasks like:
    - Crop recommendation using ML models
    - Disease detection using image classification
    - Weather data retrieval from APIs
    - Fertilizer recommendation using rule-based systems

    This class provides common utilities for tool-based agents.
    """

    def __init__(
        self,
        name: str,
        description: str,
        tool_callable: Optional[callable] = None
    ):
        """
        Initialize tool agent

        Args:
            name: Agent name
            description: Agent description
            tool_callable: Optional callable that represents the tool/model
        """
        super().__init__(name, description)
        self.tool_callable = tool_callable

    def extract_parameters(
        self,
        state: AgentState,
        required_fields: List[str]
    ) -> Dict[str, Any]:
        """
        Extract required parameters from state

        Args:
            state: Current agent state
            required_fields: List of field names required by the tool

        Returns:
            Dictionary of extracted parameters

        Raises:
            ValueError: If required fields are missing
        """
        params = {}
        missing_fields = []

        for field in required_fields:
            # Check in user_context first
            if state.get("user_context") and field in state["user_context"]:
                params[field] = state["user_context"][field]
            # Then check in state directly
            elif field in state:
                params[field] = state[field]
            else:
                missing_fields.append(field)

        if missing_fields:
            raise ValueError(
                f"{self.name}: Missing required fields: {missing_fields}"
            )

        return params

    async def execute_tool(
        self,
        params: Dict[str, Any]
    ) -> tuple[Any, float]:
        """
        Execute the tool with given parameters

        Args:
            params: Parameters for tool execution

        Returns:
            Tuple of (tool_result, latency_ms)

        Raises:
            Exception: If tool execution fails
        """
        if not self.tool_callable:
            raise ValueError(f"{self.name}: No tool callable configured")

        start_time = time.perf_counter()

        # Execute tool (handle both sync and async callables)
        import inspect
        if inspect.iscoroutinefunction(self.tool_callable):
            result = await self.tool_callable(**params)
        else:
            result = self.tool_callable(**params)

        latency_ms = (time.perf_counter() - start_time) * 1000

        return result, latency_ms

    @abstractmethod
    async def run(self, state: AgentState) -> AgentState:
        """Execute tool agent logic"""
        pass

    def health_check(self) -> Dict[str, Any]:
        """
        Check health of tool agent

        Returns:
            Health status with tool availability
        """
        status = super().health_check()
        status["tool_configured"] = self.tool_callable is not None
        status["status"] = "healthy" if status["tool_configured"] else "degraded"
        return status


# ============================================================================
# Example Concrete Implementations
# ============================================================================

class GeneralRAGAgent(RAGAgent):
    """
    Concrete implementation of RAG agent for general agricultural queries

    This agent handles queries that require knowledge retrieval from
    the vector database followed by LLM generation.
    """

    def __init__(self, embedding_service, retrieval_service, generation_service):
        super().__init__(
            name="general_rag_agent",
            description="Handles general agricultural knowledge queries using RAG",
            embedding_service=embedding_service,
            retrieval_service=retrieval_service,
            generation_service=generation_service
        )

    @track_latency("general_rag_agent")
    async def run(self, state: AgentState) -> AgentState:
        """
        Execute general RAG pipeline

        Args:
            state: Agent state with user_query

        Returns:
            Updated state with rag_output
        """
        try:
            query = state.get("user_query", "")
            if not query:
                state["error"] = "No query provided"
                return state

            # Step 1: Embed query
            query_embedding, embed_latency = await self.embed_query(query)

            # Step 2: Retrieve relevant chunks
            top_k = state.get("user_context", {}).get("top_k", 5)
            filters = state.get("user_context", {}).get("filters")

            retrieval_results, retrieve_latency = await self.retrieve_chunks(
                query_embedding=query_embedding,
                top_k=top_k,
                filters=filters
            )

            # Step 3: Generate answer
            answer, generate_latency = await self.generate_answer(
                query=query,
                retrieved_chunks=retrieval_results["chunks"]
            )

            # Update state with results using collected_findings pattern
            if state.get("collected_findings") is None:
                state["collected_findings"] = {}

            state["collected_findings"]["general_rag_agent"] = {
                "status": "success",
                "data": {
                    "answer": answer,
                    "sources": retrieval_results["sources"]
                }
            }

            # Legacy format for backward compatibility
            state["rag_output"] = {
                "answer": answer,
                "chunks": retrieval_results["chunks"],
                "sources": retrieval_results["sources"],
                "node_latencies": {
                    "embed_ms": embed_latency,
                    "retrieve_ms": retrieve_latency,
                    "generate_ms": generate_latency
                }
            }

            # Add to executed agents list
            if state.get("executed_agents") is None:
                state["executed_agents"] = []
            state["executed_agents"].append(self.name)

            logger.info(
                f"{self.name}: Generated answer "
                f"(embed: {embed_latency:.0f}ms, "
                f"retrieve: {retrieve_latency:.0f}ms, "
                f"generate: {generate_latency:.0f}ms)"
            )

            return state

        except Exception as e:
            logger.error(f"{self.name} failed: {e}", exc_info=True)
            state["error"] = f"{self.name}: {str(e)}"
            return state
