"""
RAG Configuration Management for Krishi Mitra
"""
from functools import lru_cache
from typing import Optional
from pydantic_settings import BaseSettings
from pydantic import Field


class Settings(BaseSettings):
    """Application settings for RAG system"""
    
    # Pinecone Configuration
    pinecone_api_key: str = Field(..., env="PINECONE_API_KEY")
    pinecone_environment: str = Field("us-east-1", env="PINECONE_ENVIRONMENT")
    pinecone_index_name: str = Field("krishimitra-knowledge", env="PINECONE_INDEX_NAME")
    
    # Embedding Model Configuration
    embedding_model_name: str = Field(
        "sentence-transformers/all-mpnet-base-v2", 
        env="EMBEDDING_MODEL_NAME"
    )
    embedding_dimension: int = Field(768, env="EMBEDDING_DIMENSION")
    
    # LLM Configuration
    llm_provider: str = Field("gemini", env="LLM_PROVIDER")
    gemini_api_key: str = Field(..., env="GEMINI_API_KEY")
    gemini_model: str = Field("gemini-2.5-flash-lite", env="GEMINI_MODEL")
    
    # Retrieval Configuration
    default_top_k: int = Field(5, env="DEFAULT_TOP_K")
    max_top_k: int = Field(20, env="MAX_TOP_K")
    
    # Generation Configuration
    max_tokens: int = Field(1000, env="MAX_TOKENS")
    temperature: float = Field(0.7, env="TEMPERATURE")
    
    # LangGraph Configuration
    graph_timeout: int = Field(30, env="GRAPH_TIMEOUT")  # seconds
    enable_graph_logging: bool = Field(True, env="ENABLE_GRAPH_LOGGING")
    
    # Application Configuration
    log_level: str = Field("INFO", env="LOG_LEVEL")

    # MCP Server Configuration
    mcp_weather_path: Optional[str] = Field(None, env="MCP_WEATHER_PATH")  # Local development
    mcp_weather_url: Optional[str] = Field(None, env="MCP_WEATHER_URL")    # Production
    weather_cache_ttl: int = Field(15, env="WEATHER_CACHE_TTL")  # Minutes

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        extra = "ignore"  # Ignore extra fields from .env (like MongoDB, JWT settings)


@lru_cache()
def get_settings() -> Settings:
    """Get cached settings instance"""
    return Settings()
