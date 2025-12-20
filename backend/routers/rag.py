"""
RAG API routes for Krishi Mitra
"""
from datetime import datetime, timezone

from fastapi import APIRouter, HTTPException, status
from fastapi.responses import JSONResponse

from schemas.rag import (
    QueryRequest, QueryResponse, EmbedRequest, EmbedResponse,
    HealthResponse, GraphVisualization, ErrorResponse, SourceInfo
)
from services.orchestrator import orchestrator
from services.embeddings import embedding_service
from services.retrieval import retrieval_service
from services.generation import generation_service
from core.logging import get_logger

logger = get_logger(__name__)

router = APIRouter()


@router.post("/query", response_model=QueryResponse)
async def query_endpoint(request: QueryRequest):
    """
    Main RAG endpoint: Supervisor V2 orchestrated multi-agent system

    This endpoint processes agricultural queries using the Supervisor V2 pipeline:
    1. Session Management: Load or create session for multi-turn conversations
    2. Supervisor Agent: Classify intent, plan agent execution, route to specialist agents
    3. Specialist Agents: Execute domain-specific logic (RAG, crop, fertilizer, disease, weather)
    4. Response Synthesis: Supervisor synthesizes final response from agent findings
    5. Session Persistence: Save conversation state for follow-up queries

    Supports:
    - Text queries for general agriculture, crop recommendations, fertilizer advice, weather
    - Image uploads for disease detection
    - Multi-turn conversations via session_id
    - Intent classification and agent routing
    """
    try:
        logger.info(f"Processing query via Supervisor V2: {request.query[:100]}...")

        # Build user context from request
        user_context = {}
        if request.filters:
            user_context = request.filters.copy()

        # Execute Supervisor V2 orchestrator
        # Pass session_id directly for multi-turn conversation tracking
        result = orchestrator.run(
            query=request.query,
            user_context=user_context,
            images=request.images,
            session_id=request.session_id
        )

        # Map orchestrator response to RAG API response schema
        # The orchestrator returns: answer, final_response, session_id, turn_count, etc.

        # Extract answer (supervisor's final_response takes priority)
        answer = result.get("final_response") or result.get("answer", "")

        # Extract sources (may come from RAG agent output)
        sources = []
        if result.get("sources"):
            # Convert sources to SourceInfo schema
            for source in result["sources"]:
                if isinstance(source, dict):
                    sources.append(SourceInfo(
                        source=source.get("source", "unknown"),
                        page=source.get("page"),
                        chunk_id=source.get("chunk_id", ""),
                        score=source.get("score", 0.0)
                    ))

        # Retrieved chunks are not exposed in V2 (supervisor doesn't return raw chunks)
        # Keep empty list for frontend compatibility
        retrieved_chunks = []

        # Prepare response matching QueryResponse schema
        response = QueryResponse(
            # Required fields
            answer=answer,
            sources=sources,
            retrieved_chunks=retrieved_chunks,
            latency_ms=int(result.get("total_latency_ms", 0)),

            # Optional fields
            node_latencies=result.get("node_latencies"),

            # Supervisor V2 fields
            session_id=result.get("session_id"),
            turn_count=result.get("turn_count"),
            is_active=result.get("is_active"),
            collected_findings=result.get("collected_findings"),
            executed_agents=result.get("executed_agents"),
            intent=result.get("intent"),
            confidence=result.get("confidence")
        )

        logger.info(
            f"Query processed successfully: "
            f"latency={result.get('total_latency_ms', 0):.0f}ms, "
            f"session={result.get('session_id')}, "
            f"turn={result.get('turn_count')}, "
            f"agents={result.get('executed_agents')}"
        )

        return response

    except Exception as e:
        logger.error(f"Error processing query: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error processing query: {str(e)}"
        )


@router.post("/embed", response_model=EmbedResponse)
async def embed_endpoint(request: EmbedRequest):
    """
    Generate embeddings for input text (for testing/debugging)
    """
    try:
        # Generate embeddings
        embeddings, processing_time_ms = embedding_service.embed_query(request.text)
        
        response = EmbedResponse(
            embeddings=embeddings,
            dimension=len(embeddings),
            processing_time_ms=processing_time_ms
        )
        
        logger.info(f"Generated embeddings for text in {processing_time_ms}ms")
        return response
        
    except Exception as e:
        logger.error(f"Error generating embeddings: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error generating embeddings: {str(e)}"
        )


@router.get("/health", response_model=HealthResponse)
async def health_endpoint():
    """
    Health check endpoint for Supervisor V2 orchestrator and all sub-services

    Checks:
    - Orchestrator graph compilation status
    - All specialist agents (RAG, crop, fertilizer, disease, weather)
    - Pinecone connection and index status
    - LLM service availability
    - Query classifier status
    """
    try:
        timestamp = datetime.now(timezone.utc).isoformat()

        # Check Pinecone connection
        retrieval_health = await retrieval_service.health_check()
        pinecone_status = retrieval_health.get("status", "unknown")

        # Check Supervisor V2 orchestrator
        orchestrator_health = orchestrator.health_check()
        orchestrator_status = orchestrator_health.get("status", "unknown")

        # Check LLM service
        generation_health = generation_service.health_check()

        # Determine overall status
        # System is healthy if Pinecone is connected and orchestrator is healthy
        overall_status = "ok" if (pinecone_status == "connected" and orchestrator_status == "healthy") else "degraded"

        response = HealthResponse(
            status=overall_status,
            pinecone=pinecone_status,
            langgraph=orchestrator_status,  # Use orchestrator status for backward compatibility
            timestamp=timestamp,
            details={
                "retrieval": retrieval_health,
                "orchestrator": orchestrator_health,
                "generation": generation_health,
                "agents_available": orchestrator_health.get("agents_available", {}),
                "classifier": orchestrator_health.get("classifier", {})
            }
        )

        if overall_status != "ok":
            return JSONResponse(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                content=response.model_dump()
            )

        return response

    except Exception as e:
        logger.error(f"Health check failed: {e}", exc_info=True)
        error_response = ErrorResponse(
            error="Health check failed",
            detail=str(e),
            timestamp=datetime.now(timezone.utc).isoformat()
        )
        return JSONResponse(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            content=error_response.model_dump()
        )


@router.get("/graph/visualize", response_model=GraphVisualization)
async def visualize_graph_endpoint():
    """
    Get Supervisor V2 orchestrator workflow structure for visualization

    Returns the nodes and edges of the multi-agent orchestrator graph
    for debugging and visualization purposes.

    The graph includes:
    - Session management nodes (load_session, save_session)
    - Supervisor node (brain of the system)
    - Specialist agent nodes (general_rag, crop, fertilizer, disease, weather)
    - Conditional routing edges based on supervisor decisions
    """
    try:
        graph_structure = orchestrator.get_graph_structure()

        response = GraphVisualization(
            nodes=graph_structure["nodes"],
            edges=graph_structure["edges"],
            entry_point=graph_structure["entry_point"],
            description=graph_structure["description"]
        )

        logger.info("Orchestrator graph structure retrieved successfully")
        return response

    except Exception as e:
        logger.error(f"Error getting graph structure: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error getting graph structure: {str(e)}"
        )
