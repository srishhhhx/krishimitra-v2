"""
Pydantic schemas for RAG API requests and responses
"""
from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field


class QueryRequest(BaseModel):
    """Request model for query endpoint"""
    query: str = Field(..., description="The user's question", min_length=1, max_length=1000)
    top_k: Optional[int] = Field(5, description="Number of chunks to retrieve", ge=1, le=20)
    filters: Optional[Dict[str, Any]] = Field(None, description="Optional metadata filters")
    session_id: Optional[str] = Field(None, description="Session ID for multi-turn conversations")
    images: Optional[List[str]] = Field(None, description="Base64-encoded images for disease detection")


class SourceInfo(BaseModel):
    """Information about a source document"""
    source: str = Field(..., description="Source filename")
    page: Optional[int] = Field(None, description="Page number if applicable")
    chunk_id: str = Field(..., description="Unique chunk identifier")
    score: float = Field(..., description="Similarity score")


class QueryResponse(BaseModel):
    """Response model for query endpoint"""
    answer: str = Field(..., description="Generated answer")
    sources: List[SourceInfo] = Field(default_factory=list, description="Source information")
    retrieved_chunks: List[str] = Field(default_factory=list, description="Retrieved text chunks")
    latency_ms: int = Field(..., description="Total response time in milliseconds")
    node_latencies: Optional[Dict[str, float]] = Field(None, description="Individual node latencies")

    # Supervisor V2 fields for multi-turn conversations and debugging
    session_id: Optional[str] = Field(None, description="Session ID for tracking multi-turn conversations")
    turn_count: Optional[int] = Field(None, description="Number of turns in this session")
    is_active: Optional[bool] = Field(None, description="Whether the session is still active")
    collected_findings: Optional[Dict[str, Any]] = Field(None, description="Findings collected from executed agents")
    executed_agents: Optional[List[str]] = Field(None, description="List of agents executed for this query")
    intent: Optional[str] = Field(None, description="Classified query intent")
    confidence: Optional[float] = Field(None, description="Classification confidence score")


class EmbedRequest(BaseModel):
    """Request model for embed endpoint"""
    text: str = Field(..., description="Text to embed", min_length=1, max_length=5000)


class EmbedResponse(BaseModel):
    """Response model for embed endpoint"""
    embeddings: List[float] = Field(..., description="Generated embeddings")
    dimension: int = Field(..., description="Embedding dimension")
    processing_time_ms: float = Field(..., description="Time taken to generate embeddings")


class HealthResponse(BaseModel):
    """Response model for health check"""
    status: str = Field(..., description="Overall status")
    pinecone: str = Field(..., description="Pinecone connection status")
    langgraph: str = Field(..., description="LangGraph status")
    timestamp: str = Field(..., description="Health check timestamp")
    details: Optional[Dict[str, Any]] = Field(None, description="Additional details")


class GraphNode(BaseModel):
    """Represents a node in the LangGraph workflow"""
    id: str = Field(..., description="Node identifier")
    name: str = Field(..., description="Node name")
    type: str = Field(..., description="Node type")


class GraphEdge(BaseModel):
    """Represents an edge in the LangGraph workflow"""
    source: str = Field(..., description="Source node")
    target: str = Field(..., description="Target node")
    condition: Optional[str] = Field(None, description="Edge condition if any")


class GraphVisualization(BaseModel):
    """Graph structure visualization"""
    nodes: List[GraphNode] = Field(..., description="List of nodes")
    edges: List[GraphEdge] = Field(..., description="List of edges")
    entry_point: str = Field(..., description="Entry point node")
    description: str = Field(..., description="Graph description")


class ErrorResponse(BaseModel):
    """Error response model"""
    error: str = Field(..., description="Error message")
    detail: Optional[str] = Field(None, description="Detailed error information")
    timestamp: str = Field(..., description="Error timestamp")
