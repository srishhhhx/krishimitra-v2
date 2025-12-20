"""
LangGraph orchestration pipeline for RAG workflow
"""
import time
from typing import TypedDict, List, Dict, Any, Optional
from langgraph.graph import StateGraph, END

from services.embeddings import embedding_service
from services.retrieval import retrieval_service
from services.generation import generation_service
from core.config import get_settings
from core.logging import get_logger

logger = get_logger(__name__)
settings = get_settings()


class RAGState(TypedDict):
    """State object for RAG workflow"""
    query: str
    top_k: int
    filters: Optional[Dict[str, Any]]
    
    # Intermediate results
    query_embedding: Optional[List[float]]
    retrieved_chunks: Optional[List[Dict[str, Any]]]
    sources: Optional[List[Dict[str, Any]]]
    answer: Optional[str]
    
    # Latency tracking
    embed_latency_ms: Optional[float]
    retrieve_latency_ms: Optional[float]
    generate_latency_ms: Optional[float]
    total_latency_ms: Optional[float]
    
    # Error handling
    error: Optional[str]


def embed_node(state: RAGState) -> RAGState:
    """
    EmbedNode: Convert query text to embedding vector
    """
    try:
        logger.info(f"EmbedNode: Processing query of length {len(state['query'])}")
        
        query_embedding, latency_ms = embedding_service.embed_query(state["query"])
        
        state["query_embedding"] = query_embedding
        state["embed_latency_ms"] = latency_ms
        
        return state
        
    except Exception as e:
        logger.error(f"EmbedNode failed: {e}")
        state["error"] = f"Embedding failed: {str(e)}"
        return state


def retrieve_node(state: RAGState) -> RAGState:
    """
    RetrieveNode: Fetch top-k similar chunks from Pinecone
    """
    try:
        if state.get("error"):
            return state
        
        if not state.get("query_embedding"):
            state["error"] = "No query embedding available"
            return state
        
        logger.info(f"RetrieveNode: Retrieving top {state['top_k']} chunks")
        
        results, latency_ms = retrieval_service.retrieve_chunks(
            query_embedding=state["query_embedding"],
            top_k=state["top_k"],
            filter_dict=state.get("filters")
        )
        
        state["retrieved_chunks"] = results["chunks"]
        state["sources"] = results["sources"]
        state["retrieve_latency_ms"] = latency_ms
        
        return state
        
    except Exception as e:
        logger.error(f"RetrieveNode failed: {e}")
        state["error"] = f"Retrieval failed: {str(e)}"
        return state


def generate_node(state: RAGState) -> RAGState:
    """
    GenerateNode: Generate answer using LLM with retrieved context
    """
    try:
        if state.get("error"):
            return state
        
        if not state.get("retrieved_chunks"):
            state["error"] = "No retrieved chunks available"
            return state
        
        logger.info(f"GenerateNode: Generating answer with {len(state['retrieved_chunks'])} chunks")
        
        answer, latency_ms = generation_service.generate_answer(
            query=state["query"],
            retrieved_chunks=state["retrieved_chunks"]
        )
        
        state["answer"] = answer
        state["generate_latency_ms"] = latency_ms
        
        return state
        
    except Exception as e:
        logger.error(f"GenerateNode failed: {e}")
        state["error"] = f"Generation failed: {str(e)}"
        return state


class LangGraphRAGPipeline:
    """LangGraph-based RAG pipeline orchestrator"""
    
    def __init__(self):
        self.graph = self._build_graph()
        logger.info("LangGraph RAG Pipeline initialized")
    
    def _build_graph(self) -> StateGraph:
        """
        Build the LangGraph workflow
        
        Workflow:
        START -> EmbedNode -> RetrieveNode -> GenerateNode -> END
        """
        # Create graph
        workflow = StateGraph(RAGState)
        
        # Add nodes
        workflow.add_node("embed", embed_node)
        workflow.add_node("retrieve", retrieve_node)
        workflow.add_node("generate", generate_node)
        
        # Define edges
        workflow.set_entry_point("embed")
        workflow.add_edge("embed", "retrieve")
        workflow.add_edge("retrieve", "generate")
        workflow.add_edge("generate", END)
        
        # Compile graph
        return workflow.compile()
    
    def run(
        self, 
        query: str, 
        top_k: int = 5, 
        filters: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Execute the RAG pipeline
        
        Args:
            query: User's question
            top_k: Number of chunks to retrieve
            filters: Optional metadata filters
            
        Returns:
            Complete RAG response with answer, sources, and latencies
        """
        start_time = time.time()
        
        try:
            # Initialize state
            initial_state: RAGState = {
                "query": query,
                "top_k": top_k,
                "filters": filters,
                "query_embedding": None,
                "retrieved_chunks": None,
                "sources": None,
                "answer": None,
                "embed_latency_ms": None,
                "retrieve_latency_ms": None,
                "generate_latency_ms": None,
                "total_latency_ms": None,
                "error": None
            }
            
            # Execute graph
            logger.info(f"Executing RAG pipeline for query: {query[:100]}...")
            final_state = self.graph.invoke(initial_state)
            
            # Calculate total latency
            total_latency_ms = (time.time() - start_time) * 1000
            final_state["total_latency_ms"] = total_latency_ms
            
            # Check for errors
            if final_state.get("error"):
                logger.error(f"Pipeline failed: {final_state['error']}")
                raise Exception(final_state["error"])
            
            # Log metrics
            logger.log_query_metrics(
                query=query,
                total_latency_ms=total_latency_ms,
                retrieval_latency_ms=final_state.get("retrieve_latency_ms", 0),
                generation_latency_ms=final_state.get("generate_latency_ms", 0),
                num_chunks=len(final_state.get("retrieved_chunks", [])),
                success=True
            )
            
            # Format response
            return self._format_response(final_state)
            
        except Exception as e:
            logger.error(f"Pipeline execution failed: {e}")
            raise
    
    def _format_response(self, state: RAGState) -> Dict[str, Any]:
        """
        Format the final state into API response
        
        Args:
            state: Final RAG state
            
        Returns:
            Formatted response dictionary
        """
        # Extract text chunks for response
        retrieved_chunks_text = [
            chunk.get("text", "") 
            for chunk in state.get("retrieved_chunks", [])
        ]
        
        return {
            "answer": state.get("answer", ""),
            "sources": state.get("sources", []),
            "retrieved_chunks": retrieved_chunks_text,
            "latency_ms": int(state.get("total_latency_ms", 0)),
            "node_latencies": {
                "embed_ms": state.get("embed_latency_ms", 0),
                "retrieve_ms": state.get("retrieve_latency_ms", 0),
                "generate_ms": state.get("generate_latency_ms", 0)
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
                {"id": "embed", "name": "EmbedNode", "type": "embedding"},
                {"id": "retrieve", "name": "RetrieveNode", "type": "retrieval"},
                {"id": "generate", "name": "GenerateNode", "type": "generation"}
            ],
            "edges": [
                {"source": "START", "target": "embed", "condition": None},
                {"source": "embed", "target": "retrieve", "condition": None},
                {"source": "retrieve", "target": "generate", "condition": None},
                {"source": "generate", "target": "END", "condition": None}
            ],
            "entry_point": "embed",
            "description": "LangGraph-orchestrated RAG pipeline: Embed -> Retrieve -> Generate"
        }
    
    def health_check(self) -> Dict[str, Any]:
        """
        Perform health check on the pipeline
        
        Returns:
            Health status of all components
        """
        try:
            # Test with a simple query
            test_state: RAGState = {
                "query": "test",
                "top_k": 1,
                "filters": None,
                "query_embedding": None,
                "retrieved_chunks": None,
                "sources": None,
                "answer": None,
                "embed_latency_ms": None,
                "retrieve_latency_ms": None,
                "generate_latency_ms": None,
                "total_latency_ms": None,
                "error": None
            }
            
            # Test embedding
            test_state = embed_node(test_state)
            
            if test_state.get("error"):
                return {"status": "unhealthy", "error": test_state["error"]}
            
            return {
                "status": "running",
                "nodes": ["embed", "retrieve", "generate"],
                "graph_compiled": True
            }
            
        except Exception as e:
            logger.error(f"Pipeline health check failed: {e}")
            return {
                "status": "error",
                "error": str(e)
            }


# Global pipeline instance
rag_pipeline = LangGraphRAGPipeline()
