"""
Pinecone retrieval service with embedding functionality
"""
import time
from typing import List, Dict, Any, Optional

from pinecone import Pinecone

from core.config import get_settings
from core.logging import get_logger

logger = get_logger(__name__)
settings = get_settings()


class RetrievalService:
    """Handles document retrieval from Pinecone vector database"""
    
    def __init__(self):
        self.pc = None
        self.index = None
        self._initialize()
    
    def _initialize(self):
        """Initialize Pinecone client"""
        try:
            # Initialize Pinecone with new API
            self.pc = Pinecone(api_key=settings.pinecone_api_key)
            
            # Connect to existing index
            existing_indexes = [idx.name for idx in self.pc.list_indexes()]
            if settings.pinecone_index_name not in existing_indexes:
                raise ValueError(f"Index '{settings.pinecone_index_name}' not found. Available indexes: {existing_indexes}")
            
            self.index = self.pc.Index(settings.pinecone_index_name)
            
            logger.info(f"Successfully connected to Pinecone index: {settings.pinecone_index_name}")
            
        except Exception as e:
            logger.error(f"Failed to initialize retrieval service: {e}")
            raise
    
    def retrieve_chunks(
        self, 
        query_embedding: List[float], 
        top_k: int = None, 
        filter_dict: Optional[Dict[str, Any]] = None
    ) -> tuple[Dict[str, Any], float]:
        """
        Retrieve similar chunks from Pinecone using query embedding
        
        Args:
            query_embedding: Query embedding vector
            top_k: Number of results to return
            filter_dict: Optional metadata filters
            
        Returns:
            Tuple of (retrieval results, latency in ms)
        """
        if top_k is None:
            top_k = settings.default_top_k
        
        top_k = min(top_k, settings.max_top_k)
        
        try:
            start_time = time.time()
            
            # Search in Pinecone
            search_results = self.index.query(
                vector=query_embedding,
                top_k=top_k,
                include_metadata=True,
                filter=filter_dict
            )
            
            # Process results
            processed_results = self._process_search_results(search_results)
            
            latency_ms = (time.time() - start_time) * 1000
            
            logger.log_node_execution(
                node_name="RetrieveNode",
                latency_ms=latency_ms,
                metadata={"num_chunks": len(processed_results['chunks']), "top_k": top_k}
            )
            
            return processed_results, latency_ms
            
        except Exception as e:
            logger.error(f"Error during retrieval: {e}")
            raise
    
    def _process_search_results(self, search_results) -> Dict[str, Any]:
        """
        Process raw Pinecone search results
        
        Args:
            search_results: Raw results from Pinecone query
            
        Returns:
            Processed results with chunks and sources
        """
        chunks = []
        sources = []
        
        for match in search_results.matches:
            # Extract metadata
            metadata = match.metadata or {}
            
            # Create chunk info
            chunk_info = {
                "id": match.id,
                "text": metadata.get("text", ""),
                "score": float(match.score),
                "metadata": metadata
            }
            chunks.append(chunk_info)
            
            # Create source info
            source_info = {
                "source": metadata.get("filename", "unknown"),
                "page": metadata.get("page", None),
                "chunk_id": match.id,
                "score": float(match.score)
            }
            sources.append(source_info)
        
        return {
            "chunks": chunks,
            "sources": sources
        }
    
    async def get_index_stats(self) -> Dict[str, Any]:
        """
        Get Pinecone index statistics
        
        Returns:
            Index statistics and information
        """
        try:
            stats = self.index.describe_index_stats()
            return {
                "total_vectors": stats.total_vector_count,
                "dimension": stats.dimension,
                "index_fullness": stats.index_fullness,
                "namespaces": dict(stats.namespaces) if stats.namespaces else {}
            }
        except Exception as e:
            logger.error(f"Error getting index stats: {e}")
            raise
    
    async def health_check(self) -> Dict[str, Any]:
        """
        Perform health check on retrieval service
        
        Returns:
            Health status information
        """
        try:
            # Test Pinecone connection
            stats = await self.get_index_stats()
            
            return {
                "status": "connected",
                "pinecone_index": settings.pinecone_index_name,
                "total_vectors": stats["total_vectors"]
            }
            
        except Exception as e:
            logger.error(f"Health check failed: {e}")
            return {
                "status": "disconnected",
                "error": str(e)
            }


# Global retrieval service instance
retrieval_service = RetrievalService()
