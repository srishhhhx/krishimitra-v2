"""
Disease Detection Agent

This agent handles disease detection queries using the PyTorch ResNet-9 CNN model
through the disease_detection_tool_pytorch. It processes images, optionally extracts crop
type hints from user queries, and executes disease prediction with treatment recommendations.

Key Differences from Fertilizer Agent:
- Input: Image bytes (multimodal) instead of text parameters
- LLM usage: Only for optional crop_type extraction (simple, fast)
- Processing: PyTorch ResNet-9 inference (~200-500ms) vs XGBoost (<5ms)
- No defaults: Image is required (can't default image data)
- No clarification: Returns low-confidence error instead of asking questions

Model Details:
- Architecture: ResNet-9 with residual connections
- Input Size: 256×256 RGB images
- Accuracy: 99.2% validation, 100% test
- Classes: 38 disease categories across 14 crops
- Device: Auto-detects CUDA/MPS/CPU
"""
import base64
from typing import Dict, Any, Optional

from agents.base import ToolAgent, track_latency
from schemas.agents import AgentState
from tools.disease_detection_tool_pytorch import detect_plant_disease_pytorch
from core.logging import get_logger

logger = get_logger(__name__)


class DiseaseDetectionAgent(ToolAgent):
    """
    Agent for crop disease detection using CNN image classification

    This agent:
    1. Validates that images are present in state
    2. Decodes base64 image to bytes
    3. Optionally extracts crop_type hint from user_query using LLM (fast-path: skip if no query)
    4. Executes disease detection tool with image bytes
    5. Updates state with disease detection results

    Critical Input:
        - images: List of base64-encoded images (at least one required)

    Optional Input:
        - crop_type: Can be extracted from user_query for validation
        - user_query: Used for crop_type extraction only

    Performance Target: <700ms total agent execution
        - Image decoding: ~5ms
        - Crop extraction (if needed): ~150ms
        - Disease detection: ~200-500ms
    """

    def __init__(self, generation_service=None):
        """
        Initialize Disease Detection Agent

        Args:
            generation_service: Optional service for LLM generation (used for crop_type extraction)
                               If None, will skip crop_type extraction
        """
        super().__init__(
            name="disease_detection_agent",
            description="Detects crop diseases from images using PyTorch ResNet-9 CNN and provides treatment recommendations",
            tool_callable=detect_plant_disease_pytorch
        )
        self.generation_service = generation_service

    @track_latency("disease_detection_agent")
    async def run(self, state: AgentState) -> AgentState:
        """
        Execute disease detection workflow (Orchestrator V2 Pattern)

        WORKFLOW (Multimodal Image Processing):
        1. Validate at least one image is present. If not, request clarification.
        2. Normalize base64 (strip data URI prefix)
        3. Optional LLM crop extraction (if query + LLM available)
        4. Invoke PyTorch vision tool (ResNet-9 CNN)
        5. Return results in collected_findings

        Args:
            state: Current agent state with optional images and user_query

        Returns:
            Updated state with collected_findings["disease_detection_agent"] containing:
                - status: "success" | "error" | "needs_clarification"
                - data: Disease detection result (if success)
                - error: Error message (if error)
                - clarification_question: Question for the user (if clarification needed)
        """
        # Initialize collected_findings if needed
        if "collected_findings" not in state:
            state["collected_findings"] = {}
        if "clarification_state" not in state:
            state["clarification_state"] = {}

        try:
            # Phase 1: Validate images are present, else ask for clarification
            images = state.get("images")
            if not images or len(images) == 0:
                clarification_question = "I need an image to detect the disease. Please upload a photo of the affected plant."
                logger.warning(f"{self.name}: {clarification_question}")

                # Set findings for the supervisor to know the status
                state["collected_findings"][self.name] = {
                    "status": "needs_clarification",
                    "missing_fields": ["images"],
                    "clarification_question": clarification_question
                }
                
                # Set the clarification_state for the supervisor's clarification logic
                state["clarification_state"][self.name] = {
                    "needs_clarification": True,
                    "question_for_user": clarification_question,
                    "agent_waiting": self.name,
                    "requested_fields": ["images"]
                }
                
                self._add_to_executed_agents(state)
                return state

            # Phase 2: Normalize base64 image (strip data URI prefix)
            logger.info(f"{self.name}: Processing {len(images)} image(s)")
            image_base64 = images[0]

            # Strip data URI prefix if present (data:image/jpeg;base64,...)
            if image_base64.startswith('data:'):
                if ';base64,' in image_base64:
                    image_base64 = image_base64.split(';base64,')[1]
                else:
                    error_msg = "Invalid data URI format (missing ';base64,' marker)"
                    logger.error(f"{self.name}: {error_msg}")
                    state["collected_findings"]["disease_detection_agent"] = {
                        "status": "error",
                        "error": error_msg,
                        "help": "Please ensure the image is properly base64-encoded."
                    }
                    self._add_to_executed_agents(state)
                    return state

            logger.info(f"{self.name}: Image base64 ready ({len(image_base64)} chars)")

            # Phase 3: Extract crop_type from user_query (optional, fast-path: skip if no query)
            user_query = state.get("user_query", "")
            crop_type_hint = None

            if user_query and self.generation_service:
                # Use LLM to extract crop type (async)
                crop_type_hint = await self._extract_crop_type_with_llm(user_query)
                if crop_type_hint:
                    logger.info(f"{self.name}: Extracted crop type hint: {crop_type_hint}")
            elif user_query:
                logger.info(f"{self.name}: User query provided but no generation service, skipping crop extraction")
            else:
                logger.info(f"{self.name}: No user query, skipping crop type extraction")

            # Phase 4: Execute disease detection tool (PyTorch ResNet-9 CNN)
            # Tool expects: image_base64 (str), crop_type_hint (str|None), confidence_threshold (float)
            result = self.tool_callable.invoke({
                "image_base64": image_base64,
                "crop_type_hint": crop_type_hint,
                "confidence_threshold": 0.7
            })

            # Phase 5: Update state with results (V2 Pattern)
            if "error" in result:
                # Low confidence or tool failure
                logger.warning(f"{self.name}: Tool returned error: {result['error']}")
                state["collected_findings"]["disease_detection_agent"] = {
                    "status": "error",
                    "error": result["error"],
                    "help": result.get("help", "Please provide a clearer image or try again."),
                    # Include partial data if available (for debugging)
                    "confidence_percentage": result.get("confidence_percentage"),
                    "predicted_class": result.get("predicted_class")
                }
            else:
                # Successful detection
                logger.info(
                    f"{self.name}: Detected {result['disease_name']} on {result['crop']} "
                    f"(confidence: {result['confidence_percentage']}%, severity: {result['severity']})"
                )
                state["collected_findings"]["disease_detection_agent"] = {
                    "status": "success",
                    "data": result
                }

            # Add to executed agents
            self._add_to_executed_agents(state)

            return state

        except Exception as e:
            logger.error(f"{self.name} failed: {e}", exc_info=True)
            state["collected_findings"]["disease_detection_agent"] = {
                "status": "error",
                "error": f"Internal error: {str(e)}"
            }
            return state

    def _decode_base64_image(self, image_data: str) -> bytes:
        """
        Decode base64-encoded image to bytes

        Handles both data URI format (data:image/jpeg;base64,<data>) and raw base64.

        Args:
            image_data: Base64-encoded image string

        Returns:
            Raw image bytes

        Raises:
            ValueError: If decoding fails
        """
        try:
            # Handle data URI format
            if image_data.startswith("data:"):
                # Format: data:image/jpeg;base64,<base64_data>
                if "base64," in image_data:
                    image_data = image_data.split("base64,")[1]
                else:
                    raise ValueError("Data URI does not contain 'base64,' marker")

            # Decode base64
            image_bytes = base64.b64decode(image_data)

            if len(image_bytes) == 0:
                raise ValueError("Decoded image is empty")

            return image_bytes

        except Exception as e:
            raise ValueError(f"Failed to decode base64 image: {str(e)}")

    async def _extract_crop_type_with_llm(self, query: str) -> Optional[str]:
        """
        Extract crop type from user query using LLM

        This is a simple extraction task - much simpler than fertilizer parameter extraction.
        We only need to extract a single crop name.

        Args:
            query: User's natural language query

        Returns:
            Crop type string or None if not found

        Example:
            Query: "My tomato plant has brown spots on leaves"
            Returns: "tomato"
        """
        extraction_prompt = f"""
Extract the crop type from this query. Return ONLY the crop name in lowercase, or "null" if no crop is mentioned.

Query: "{query}"

Examples:
Query: "My tomato plant has brown spots"
Output: tomato

Query: "What's wrong with my potato leaves?"
Output: potato

Query: "This corn looks sick"
Output: corn

Query: "My plant is diseased"
Output: null

Return only the crop name (one word, lowercase) or "null". No explanations.
"""

        try:
            # Call generation service (sync method, no await - wrapped by run_async_agent)
            response, _ = self.generation_service.generate_answer(
                query=extraction_prompt,
                retrieved_chunks=[],
                max_tokens=10,  # Very short response needed
                temperature=0.0
            )

            # Parse response
            crop_type = response.strip().lower()

            # Handle "null" or empty responses
            if crop_type in ["null", "none", "", "unknown"]:
                logger.info(f"{self.name}: No crop type found in query")
                return None

            # Clean up response (remove quotes, periods, etc.)
            crop_type = crop_type.strip('."\'')

            # Validate it's a single word (crop names should be simple)
            if len(crop_type.split()) > 2:
                logger.warning(f"{self.name}: Extracted crop type too long: {crop_type}")
                return None

            logger.info(f"{self.name}: Successfully extracted crop type: {crop_type}")
            return crop_type

        except Exception as e:
            logger.error(f"{self.name}: Crop type extraction failed: {e}", exc_info=True)
            # Gracefully fail - crop type is optional
            return None

    def _add_to_executed_agents(self, state: AgentState) -> None:
        """
        Add this agent to the executed_agents list in state

        Args:
            state: Current agent state
        """
        if state.get("executed_agents") is None:
            state["executed_agents"] = []
        if self.name not in state["executed_agents"]:
            state["executed_agents"].append(self.name)

    def health_check(self) -> Dict[str, Any]:
        """
        Check health of disease detection agent and its dependencies

        Returns:
            Health status dictionary with service availability
        """
        status = super().health_check()

        # Check generation service availability (optional)
        status["generation_service_available"] = self.generation_service is not None

        # Check if tool callable is configured
        status["tool_configured"] = self.tool_callable is not None

        # Overall health (generation service is optional, tool is required)
        all_ok = status["tool_configured"]
        status["status"] = "healthy" if all_ok else "degraded"

        if not status["generation_service_available"]:
            status["details"] = "Generation service not available - crop type extraction disabled"

        return status
