"""
Embedding service for query vectorization
"""
import time
from typing import List
from sentence_transformers import SentenceTransformer

from core.config import get_settings
from core.logging import get_logger

logger = get_logger(__name__)
settings = get_settings()


class EmbeddingService:
    """Handles text embedding using SentenceTransformers"""
    
    def __init__(self):
        self.model = None
        self._initialize()
    
    def _initialize(self):
        """Initialize embedding model"""
        try:
            logger.info(f"Loading embedding model: {settings.embedding_model_name}")
            self.model = SentenceTransformer(settings.embedding_model_name)
            logger.info(f"Embedding model loaded successfully. Dimension: {self.model.get_sentence_embedding_dimension()}")
        except Exception as e:
            logger.error(f"Failed to initialize embedding model: {e}")
            raise
    
    def embed_query(self, query: str) -> tuple[List[float], float]:
        """
        Generate embeddings for a query string
        
        Args:
            query: Input query string
            
        Returns:
            Tuple of (embedding vector, latency in ms)
        """
        try:
            start_time = time.time()
            
            # Generate embeddings
            embeddings = self.model.encode([query])
            embedding_vector = embeddings[0].tolist()
            
            latency_ms = (time.time() - start_time) * 1000
            
            logger.log_node_execution(
                node_name="EmbedNode",
                latency_ms=latency_ms,
                metadata={"query_length": len(query), "embedding_dim": len(embedding_vector)}
            )
            
            return embedding_vector, latency_ms
            
        except Exception as e:
            logger.error(f"Error generating embeddings: {e}")
            raise
    
    def get_dimension(self) -> int:
        """Get embedding dimension"""
        return self.model.get_sentence_embedding_dimension()


# Global embedding service instance
embedding_service = EmbeddingService()
