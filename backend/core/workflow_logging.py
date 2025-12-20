"""
Enhanced Workflow Logging for Krishi Mitra Orchestrator

This module provides beautiful, structured logging for the entire orchestrator workflow,
making it easy to track requests through the multi-agent system.
"""

from typing import Dict, Any, List, Optional
from core.logging import get_logger

logger = get_logger(__name__)


class WorkflowLogger:
    """Structured logging for orchestrator workflows"""

    @staticmethod
    def log_request_start(query: str, session_id: Optional[str] = None, images: Optional[list] = None):
        """Log the start of a new request"""
        logger.info("")
        logger.info("╔" + "═" * 80 + "╗")
        logger.info("║" + " 🚀 ORCHESTRATOR V2 - NEW REQUEST ".center(80) + "║")
        logger.info("╠" + "═" * 80 + "╣")
        logger.info(f"║  📝 Query: {query[:62]:<62}  ║")
        logger.info(f"║  🔑 Session: {(session_id or 'NEW')[:62]:<62}  ║")
        logger.info(f"║  📷 Images: {(str(len(images)) + ' image(s)' if images else 'None')[:62]:<62}  ║")
        logger.info("╚" + "═" * 80 + "╝")
        logger.info("")

    @staticmethod
    def log_session_event(event: str, session_id: str, turn_count: int = 0):
        """Log session management events"""
        logger.info("┌" + "─" * 80 + "┐")
        logger.info(f"│  💾 SESSION {event.upper():<65}│")
        logger.info(f"│     Session ID: {session_id[:60]:<60}│")
        if turn_count:
            logger.info(f"│     Turn: {turn_count:<70}│")
        logger.info("└" + "─" * 80 + "┘")

    @staticmethod
    def log_supervisor_start(state: Dict[str, Any]):
        """Log supervisor node execution start"""
        logger.info("")
        logger.info("┏" + "━" * 80 + "┓")
        logger.info("┃" + " 🧠 SUPERVISOR AGENT - ORCHESTRATION ".center(80) + "┃")
        logger.info("┣" + "━" * 80 + "┫")
        logger.info(f"┃  Current Plan: {str(state.get('agent_plan', []))[:61]:<61}┃")
        logger.info(f"┃  Executed Agents: {str(state.get('executed_agents', []))[:57]:<57}┃")
        logger.info("┗" + "━" * 80 + "┛")

    @staticmethod
    def log_classification(intent: str, agents: List[str], reasoning: str = ""):
        """Log query classification results"""
        logger.info("")
        logger.info("┌" + "─" * 80 + "┐")
        logger.info("│" + " 🎯 QUERY CLASSIFICATION ".center(80) + "│")
        logger.info("├" + "─" * 80 + "┤")
        logger.info(f"│  Intent: {intent[:67]:<67}│")
        logger.info(f"│  Agents: {str(agents)[:67]:<67}│")
        if reasoning:
            # Split reasoning into multiple lines if too long
            lines = [reasoning[i:i+67] for i in range(0, len(reasoning), 67)]
            logger.info(f"│  Reasoning: {lines[0]:<63}│")
            for line in lines[1:]:
                logger.info(f"│             {line:<63}│")
        logger.info("└" + "─" * 80 + "┘")

    @staticmethod
    def log_routing(from_node: str, to_node: str):
        """Log routing decision"""
        logger.info("")
        logger.info(f"╭{'─' * 80}╮")
        logger.info(f"│  🔀 ROUTING: {from_node} → {to_node:<58}│")
        logger.info(f"╰{'─' * 80}╯")

    @staticmethod
    def log_agent_start(agent_name: str, query: str = ""):
        """Log agent execution start"""
        logger.info("")
        logger.info("╔" + "═" * 80 + "╗")
        logger.info("║" + f" ⚡ EXECUTING: {agent_name.upper()} ".center(80) + "║")
        logger.info("╠" + "═" * 80 + "╣")
        if query:
            logger.info(f"║  Query: {query[:69]:<69}║")
        logger.info("╚" + "═" * 80 + "╝")

    @staticmethod
    def log_agent_complete(agent_name: str, status: str, latency_ms: float, result_summary: str = ""):
        """Log agent execution completion"""
        status_emoji = {
            "success": "✅",
            "error": "❌",
            "needs_clarification": "❓"
        }.get(status, "⚠️")

        logger.info("")
        logger.info("┌" + "─" * 80 + "┐")
        logger.info(f"│  {status_emoji} {agent_name.upper()} COMPLETE - {status.upper():<51}│")
        logger.info(f"│     Latency: {latency_ms:.2f}ms{'':<58}│")
        if result_summary:
            # Split summary into multiple lines
            lines = [result_summary[i:i+67] for i in range(0, len(result_summary), 67)]
            logger.info(f"│     Result: {lines[0]:<64}│")
            for line in lines[1:]:
                logger.info(f"│             {line:<64}│")
        logger.info("└" + "─" * 80 + "┘")

    @staticmethod
    def log_findings_summary(collected_findings: Dict[str, Any]):
        """Log summary of collected findings"""
        logger.info("")
        logger.info("┏" + "━" * 80 + "┓")
        logger.info("┃" + " 📊 COLLECTED FINDINGS SUMMARY ".center(80) + "┃")
        logger.info("┣" + "━" * 80 + "┫")

        for agent_name, finding in collected_findings.items():
            status = finding.get("status", "unknown")
            status_emoji = {
                "success": "✅",
                "error": "❌",
                "needs_clarification": "❓"
            }.get(status, "⚠️")

            logger.info(f"┃  {status_emoji} {agent_name:<72}┃")

            if status == "success":
                data = finding.get("data", {})
                if isinstance(data, dict):
                    # Show key fields
                    for key, value in list(data.items())[:3]:
                        value_str = str(value)[:55]
                        logger.info(f"┃      {key}: {value_str:<61}┃")
            elif status == "error":
                error = finding.get("error", "Unknown")[:62]
                logger.info(f"┃      Error: {error:<63}┃")
            elif status == "needs_clarification":
                missing = finding.get("missing_fields", [])
                logger.info(f"┃      Missing: {str(missing)[:61]:<61}┃")

        logger.info("┗" + "━" * 80 + "┛")

    @staticmethod
    def log_synthesis(final_response: str, char_count: int):
        """Log response synthesis"""
        logger.info("")
        logger.info("╔" + "═" * 80 + "╗")
        logger.info("║" + " 🎯 RESPONSE SYNTHESIS ".center(80) + "║")
        logger.info("╠" + "═" * 80 + "╣")
        logger.info(f"║  Response length: {char_count} characters{'':<52}║")

        # Show preview of response (first 150 chars)
        preview = final_response[:150].replace('\n', ' ')
        logger.info(f"║  Preview: {preview:<66}║")
        logger.info("╚" + "═" * 80 + "╝")

    @staticmethod
    def log_request_complete(session_id: str, latency_ms: float, executed_agents: List[str]):
        """Log request completion"""
        logger.info("")
        logger.info("╔" + "═" * 80 + "╗")
        logger.info("║" + " ✅ REQUEST COMPLETE ".center(80) + "║")
        logger.info("╠" + "═" * 80 + "╣")
        logger.info(f"║  Session: {session_id[:66]:<66}║")
        logger.info(f"║  Total Latency: {latency_ms:.2f}ms{'':<60}║")
        logger.info(f"║  Agents Executed: {str(executed_agents)[:60]:<60}║")
        logger.info("╚" + "═" * 80 + "╝")
        logger.info("")

    @staticmethod
    def log_error(component: str, error_msg: str):
        """Log error"""
        logger.error("")
        logger.error("╔" + "═" * 80 + "╗")
        logger.error("║" + " ❌ ERROR ".center(80) + "║")
        logger.error("╠" + "═" * 80 + "╣")
        logger.error(f"║  Component: {component[:65]:<65}║")
        logger.error(f"║  Error: {error_msg[:70]:<70}║")
        logger.error("╚" + "═" * 80 + "╝")
        logger.error("")


# Convenience instance
workflow_log = WorkflowLogger()
