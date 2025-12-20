"""
Structured Logging for RAG Pipeline
"""
import logging
import sys
from typing import Any, Dict
import json
from datetime import datetime


class StructuredLogger:
    """Structured logger for better observability"""
    
    def __init__(self, name: str):
        self.logger = logging.getLogger(name)
        self.logger.setLevel(logging.INFO)
        
        # Create console handler with structured format
        handler = logging.StreamHandler(sys.stdout)
        handler.setLevel(logging.INFO)
        
        # Use JSON formatter for structured logs
        formatter = logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        )
        handler.setFormatter(formatter)
        
        if not self.logger.handlers:
            self.logger.addHandler(handler)
    
    def log_node_execution(
        self, 
        node_name: str, 
        latency_ms: float, 
        status: str = "success",
        metadata: Dict[str, Any] = None
    ):
        """Log node execution with timing"""
        log_data = {
            "node": node_name,
            "latency_ms": latency_ms,
            "status": status,
            "timestamp": datetime.utcnow().isoformat()
        }
        if metadata:
            log_data.update(metadata)
        
        self.logger.info(f"Node Execution: {json.dumps(log_data)}")
    
    def log_query_metrics(
        self,
        query: str,
        total_latency_ms: float,
        retrieval_latency_ms: float,
        generation_latency_ms: float,
        num_chunks: int,
        success: bool = True
    ):
        """Log query processing metrics"""
        log_data = {
            "query_length": len(query),
            "total_latency_ms": total_latency_ms,
            "retrieval_latency_ms": retrieval_latency_ms,
            "generation_latency_ms": generation_latency_ms,
            "num_chunks": num_chunks,
            "success": success,
            "timestamp": datetime.utcnow().isoformat()
        }
        
        self.logger.info(f"Query Metrics: {json.dumps(log_data)}")
    
    def info(self, message: str, **kwargs):
        """Log info message"""
        if kwargs:
            message = f"{message} - {json.dumps(kwargs)}"
        self.logger.info(message)
    
    def error(self, message: str, **kwargs):
        """Log error message"""
        if kwargs:
            message = f"{message} - {json.dumps(kwargs)}"
        self.logger.error(message)
    
    def warning(self, message: str, **kwargs):
        """Log warning message"""
        if kwargs:
            message = f"{message} - {json.dumps(kwargs)}"
        self.logger.warning(message)


def get_logger(name: str) -> StructuredLogger:
    """Get a structured logger instance"""
    return StructuredLogger(name)
