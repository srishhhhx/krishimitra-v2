"""
General RAG Agent Wrapper (Orchestrator V2 Integration)

This agent wraps the existing LangGraph RAG pipeline and integrates it
into the multi-agent orchestration system.

**Key Features:**
- Wraps existing rag_pipeline from services.langgraph_pipeline
- No clarification needed (works with any query)
- Uses collected_findings pattern for orchestrator integration
- Async execution with sync RAG pipeline (uses executor)

**Integration Pattern:**
- Input: state["user_query"]
- Output: state["collected_findings"]["general_rag_agent"]
"""
import asyncio
from typing import Dict, Any

from agents.base import RAGAgent, track_latency
from schemas.agents import AgentState
from services.langgraph_pipeline import rag_pipeline
from core.logging import get_logger

logger = get_logger(__name__)


class GeneralRAGAgentWrapper(RAGAgent):
    """
    Wrapper for existing LangGraph RAG pipeline

    This agent provides a clean integration between the existing RAG
    pipeline and the new multi-agent orchestration system.

    **No Clarification Needed:**
    Unlike crop/fertilizer agents, this agent works with ANY query.
    It doesn't require specific parameters or user context.

    **Async Execution:**
    The existing RAG pipeline is sync, so we use asyncio.to_thread()
    to execute it without blocking the event loop.
    """

    def __init__(self):
        """
        Initialize General RAG Agent Wrapper

        Note: We don't need to pass services since we're using
        the existing rag_pipeline singleton.
        """
        super().__init__(
            name="general_rag_agent",
            description="Handles general agricultural knowledge queries using RAG pipeline",
            embedding_service=None,  # Using rag_pipeline instead
            retrieval_service=None,  # Using rag_pipeline instead
            generation_service=None  # Using rag_pipeline instead
        )

    @track_latency("general_rag_agent")
    async def run(self, state: AgentState) -> AgentState:
        """
        Execute RAG pipeline for general agricultural queries

        Workflow:
        1. Extract query from state
        2. Execute RAG pipeline (async via executor)
        3. Format results in collected_findings pattern
        4. Return updated state

        Args:
            state: Agent state with user_query

        Returns:
            Updated state with collected_findings["general_rag_agent"]

        Example:
            Input state:
                {"user_query": "What is the best fertilizer for wheat?"}

            Output state:
                {
                    "collected_findings": {
                        "general_rag_agent": {
                            "status": "success",
                            "data": {
                                "answer": "For wheat cultivation, NPK fertilizers...",
                                "sources": [...],
                                "retrieved_chunks": [...],
                                "latency_ms": 2300
                            }
                        }
                    },
                    "executed_agents": ["general_rag_agent"]
                }
        """
        try:
            # Extract query
            query = state.get("user_query", "")
            if not query:
                logger.warning(f"{self.name}: No query provided")
                state["collected_findings"] = state.get("collected_findings", {})
                state["collected_findings"][self.name] = {
                    "status": "error",
                    "error": "No query provided"
                }
                return state

            logger.info(f"{self.name}: Processing query: {query[:100]}...")

            # Extract optional parameters
            top_k = state.get("user_context", {}).get("top_k", 5)
            filters = state.get("user_context", {}).get("filters")

            # Execute RAG pipeline (sync → async via executor)
            # This prevents blocking the event loop during I/O operations
            loop = asyncio.get_event_loop()
            rag_output = await loop.run_in_executor(
                None,  # Default executor
                rag_pipeline.run,
                query,
                top_k,
                filters
            )

            # Format as structured finding
            if state.get("collected_findings") is None:
                state["collected_findings"] = {}

            state["collected_findings"][self.name] = {
                "status": "success",
                "data": {
                    "answer": rag_output["answer"],
                    "sources": rag_output.get("sources", []),
                    "retrieved_chunks": rag_output.get("retrieved_chunks", []),
                    "latency_ms": rag_output.get("latency_ms", 0),
                    "node_latencies": rag_output.get("node_latencies", {})
                }
            }

            # Add to executed agents list
            if state.get("executed_agents") is None:
                state["executed_agents"] = []
            state["executed_agents"].append(self.name)

            logger.info(
                f"{self.name}: Successfully retrieved answer "
                f"(latency: {rag_output.get('latency_ms', 0):.0f}ms, "
                f"sources: {len(rag_output.get('sources', []))})"
            )

            return state

        except Exception as e:
            logger.error(f"{self.name} failed: {e}", exc_info=True)

            # Store error in collected_findings
            if state.get("collected_findings") is None:
                state["collected_findings"] = {}

            state["collected_findings"][self.name] = {
                "status": "error",
                "error": str(e)
            }

            return state

    def health_check(self) -> Dict[str, Any]:
        """
        Check health of RAG agent and pipeline

        Returns:
            Health status with pipeline availability
        """
        try:
            # Test RAG pipeline health
            pipeline_health = rag_pipeline.health_check()

            return {
                "status": pipeline_health.get("status", "unknown"),
                "name": self.name,
                "description": self.description,
                "pipeline_status": pipeline_health.get("status"),
                "pipeline_nodes": pipeline_health.get("nodes", []),
                "pipeline_compiled": pipeline_health.get("graph_compiled", False)
            }
        except Exception as e:
            logger.error(f"{self.name} health check failed: {e}")
            return {
                "status": "unhealthy",
                "name": self.name,
                "description": self.description,
                "error": str(e)
            }
