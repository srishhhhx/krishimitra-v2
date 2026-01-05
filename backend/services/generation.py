"""
LLM generation service supporting Gemini
"""
import time
from typing import List, Dict, Any, Optional

import google.generativeai as genai

from core.config import get_settings
from core.logging import get_logger

logger = get_logger(__name__)
settings = get_settings()


class GenerationService:
    """Handles text generation using Gemini LLM"""

    def __init__(self):
        self.gemini_model = None
        self._initialize()
    
    def _initialize(self):
        """Initialize Gemini LLM"""
        try:
            if not settings.gemini_api_key:
                raise ValueError("GEMINI_API_KEY is required")
            
            genai.configure(api_key=settings.gemini_api_key)
            
            # Configure safety settings to be permissive for agricultural content
            safety_settings = {
                "HARM_CATEGORY_HARASSMENT": "BLOCK_NONE",
                "HARM_CATEGORY_HATE_SPEECH": "BLOCK_NONE",
                "HARM_CATEGORY_SEXUALLY_EXPLICIT": "BLOCK_NONE",
                "HARM_CATEGORY_DANGEROUS_CONTENT": "BLOCK_NONE",
            }
            
            self.gemini_model = genai.GenerativeModel(
                settings.gemini_model,
                safety_settings=safety_settings
            )
            logger.info(f"Initialized Gemini model: {settings.gemini_model}")
                
        except Exception as e:
            logger.error(f"Failed to initialize generation service: {e}")
            raise
    
    def _create_rag_prompt(self, query: str, retrieved_chunks: List[Dict[str, Any]]) -> str:
        """
        Create a RAG prompt combining query and retrieved context
        
        Args:
            query: User's question
            retrieved_chunks: List of retrieved document chunks
            
        Returns:
            Formatted prompt string
        """
        # Combine retrieved text with metadata
        context_texts = []
        for i, chunk in enumerate(retrieved_chunks, 1):
            text = chunk.get("text", "")
            metadata = chunk.get("metadata", {})
            
            # Extract useful metadata
            filename = metadata.get("filename", "unknown")
            state = metadata.get("state", "")
            crop = metadata.get("crop", "")
            season = metadata.get("season", "")
            
            # Build context header with available metadata
            header_parts = [f"Source {i}"]
            if state:
                header_parts.append(f"State: {state}")
            if crop:
                header_parts.append(f"Crop: {crop}")
            if season:
                header_parts.append(f"Season: {season}")
            header_parts.append(f"File: {filename}")
            
            header = "[" + " | ".join(header_parts) + "]"
            context_texts.append(f"{header}\n{text}")
        
        combined_context = "\n\n".join(context_texts)
        
        # Create RAG prompt
        prompt = f"""You are KrishiMitra, an AI assistant specialized in Indian agriculture. Answer the farmer's question using the information provided below.

Context Information:
{combined_context}

Question: {query}

Instructions:
1. Provide a helpful, direct answer using the information available
2. When asked about specific regions/states:
   - Use exact regional data if available
   - Otherwise, provide general agricultural guidelines that apply to similar conditions
   - Mention the region/state naturally in your answer when relevant
3. Combine information from multiple sources to give complete, practical answers
4. Include specific details like:
   - Crop varieties and characteristics
   - NPK values and fertilizer recommendations
   - Sowing times, spacing, and seed rates
   - Pest/disease management practices
   - Regional or seasonal variations
5. Write in simple, conversational language as if advising a farmer directly
6. Be confident and helpful - focus on what you can tell them
7. Only mention lack of information if the question is completely outside agriculture or if truly no relevant information exists

Answer the question naturally and helpfully:"""
        
        return prompt

    def generate_answer(
        self,
        query: str,
        retrieved_chunks: List[Dict[str, Any]],
        max_tokens: Optional[int] = None,
        temperature: Optional[float] = None
    ) -> tuple[str, float]:
        """
        Generate an answer using retrieved context

        Args:
            query: User's question
            retrieved_chunks: Retrieved document chunks
            max_tokens: Maximum tokens to generate
            temperature: Generation temperature

        Returns:
            Tuple of (generated answer, latency in ms)
        """
        if max_tokens is None:
            max_tokens = settings.max_tokens
        if temperature is None:
            temperature = settings.temperature

        try:
            start_time = time.time()

            # Create RAG prompt
            prompt = self._create_rag_prompt(query, retrieved_chunks)

            # Generate response using Gemini
            response = self._generate_with_gemini_sync(prompt, max_tokens, temperature)
            
            latency_ms = (time.time() - start_time) * 1000
            
            logger.log_node_execution(
                node_name="GenerateNode",
                latency_ms=latency_ms,
                metadata={"provider": settings.llm_provider, "model": response["model"]}
            )
            
            return response["text"], latency_ms
            
        except Exception as e:
            logger.error(f"Error generating answer: {e}")
            raise
    
    def _generate_with_gemini_sync(
        self, 
        prompt: str, 
        max_tokens: int, 
        temperature: float,
        max_retries: int = 3
    ) -> Dict[str, Any]:
        """
        Generate response using Gemini (synchronous) with retry logic.
        
        Args:
            prompt: The prompt to send to Gemini
            max_tokens: Maximum tokens to generate
            temperature: Generation temperature
            max_retries: Maximum retry attempts for transient errors
            
        Returns:
            Dict with 'text' and 'model' keys
            
        Raises:
            Exception: If all retries exhausted or non-retryable error
        """
        last_exception = None
        
        for attempt in range(max_retries + 1):
            try:
                generation_config = genai.types.GenerationConfig(
                    max_output_tokens=max_tokens,
                    temperature=temperature,
                )
                
                response = self.gemini_model.generate_content(
                    prompt,
                    generation_config=generation_config
                )
                
                # Extract text from response, handling multi-part responses
                text = ""
                
                # Check if response was blocked
                if not response.candidates:
                    logger.error(f"Gemini response blocked. Prompt feedback: {response.prompt_feedback}")
                    raise ValueError(f"Response blocked by Gemini safety filters: {response.prompt_feedback}")
                
                try:
                    # Try simple text accessor first
                    text = response.text
                except (ValueError, AttributeError) as e:
                    # If that fails, extract from parts
                    logger.warning(f"Simple text accessor failed: {e}. Trying parts extraction.")
                    if response.candidates:
                        candidate = response.candidates[0]
                        
                        # Check if candidate was blocked
                        if hasattr(candidate, 'finish_reason') and candidate.finish_reason != 1:  # 1 = STOP (normal)
                            logger.error(f"Candidate finish reason: {candidate.finish_reason}")
                        
                        if hasattr(candidate, 'content') and hasattr(candidate.content, 'parts'):
                            for part in candidate.content.parts:
                                if hasattr(part, 'text'):
                                    text += part.text
                    
                    if not text:
                        logger.error(f"Full response: {response}")
                        raise ValueError(f"No text content in Gemini response. Finish reason: {candidate.finish_reason if response.candidates else 'No candidates'}")
                
                return {
                    "text": text,
                    "model": settings.gemini_model
                }
                
            except Exception as e:
                last_exception = e
                error_str = str(e).lower()
                
                # Check if this is a retryable error (429 quota or 503 service unavailable)
                is_quota_error = "429" in error_str or "quota" in error_str or "resource exhausted" in error_str
                is_service_error = "503" in error_str or "service unavailable" in error_str
                
                if (is_quota_error or is_service_error) and attempt < max_retries:
                    # Exponential backoff: 2^attempt seconds (2, 4, 8...)
                    wait_time = 2 ** (attempt + 1)
                    logger.warning(
                        f"Gemini API error (attempt {attempt + 1}/{max_retries + 1}): {e}. "
                        f"Retrying in {wait_time}s..."
                    )
                    time.sleep(wait_time)
                    continue
                else:
                    # Non-retryable error or max retries exhausted
                    if attempt == max_retries:
                        logger.error(f"Gemini API failed after {max_retries + 1} attempts: {e}")
                    else:
                        logger.error(f"Non-retryable Gemini error: {e}")
                    raise
        
        # Should not reach here, but just in case
        if last_exception:
            raise last_exception
        raise RuntimeError("Unexpected state in retry loop")
    
    def health_check(self) -> Dict[str, Any]:
        """
        Perform health check on generation service
        
        Returns:
            Health status information
        """
        try:
            # Simple check - verify Gemini model is initialized
            if self.gemini_model:
                return {
                    "status": "running",
                    "provider": "gemini",
                    "model": settings.gemini_model
                }
            else:
                return {
                    "status": "not_initialized",
                    "provider": "gemini"
                }
            
        except Exception as e:
            logger.error(f"Generation health check failed: {e}")
            return {
                "status": "error",
                "provider": "gemini",
                "error": str(e)
            }


# Global generation service instance
generation_service = GenerationService()
