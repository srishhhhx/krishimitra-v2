#!/usr/bin/env python3
"""
Interactive Test Script for Supervisor V2 Orchestrator

This script provides a comprehensive interactive interface to test the entire
Supervisor V2 multi-agent pipeline with detailed query flow insights.

Features:
- Test all agents (crop, fertilizer, weather, disease, RAG)
- Multi-turn conversation support with session management
- Detailed query flow visualization
- Debug mode with collected_findings inspection
- Performance metrics and latency breakdown
- Example queries for each agent type

Usage:
    python test_supervisor_v2_interactive.py

Commands:
    - Type your query and press Enter
    - 'help' - Show example queries for all agents
    - 'examples <agent>' - Show examples for specific agent (crop/fertilizer/weather/disease/rag)
    - 'debug' - Toggle debug mode (shows collected_findings, routing details)
    - 'session' - Show current session info
    - 'reset' - Reset session (start fresh conversation)
    - 'stats' - Show performance statistics
    - 'quit' or 'exit' - Exit the program
"""

import sys
from pathlib import Path
from typing import Dict, Any, List
from datetime import datetime

# Add backend to path
sys.path.insert(0, str(Path(__file__).parent))

from services.orchestrator import orchestrator
from core.logging import get_logger

# Setup logging
logger = get_logger(__name__)

# ANSI color codes for beautiful output
class Colors:
    HEADER = '\033[95m'
    OKBLUE = '\033[94m'
    OKCYAN = '\033[96m'
    OKGREEN = '\033[92m'
    WARNING = '\033[93m'
    FAIL = '\033[91m'
    ENDC = '\033[0m'
    BOLD = '\033[1m'
    UNDERLINE = '\033[4m'
    DIM = '\033[2m'

    # Agent-specific colors
    CROP = '\033[92m'       # Green
    FERTILIZER = '\033[93m' # Yellow
    WEATHER = '\033[96m'    # Cyan
    DISEASE = '\033[91m'    # Red
    RAG = '\033[95m'        # Magenta

# Emoji for visual appeal
EMOJI = {
    'crop': '🌱',
    'fertilizer': '🌾',
    'weather': '🌤️',
    'disease': '🔍',
    'rag': '📚',
    'success': '✅',
    'error': '❌',
    'clarification': '❓',
    'routing': '🔀',
    'session': '🔑',
    'latency': '⚡',
    'thinking': '🧠',
}

class SessionStats:
    """Track session statistics"""
    def __init__(self):
        self.queries_processed = 0
        self.total_latency_ms = 0
        self.agent_usage = {}
        self.errors = 0
        self.clarifications = 0

    def update(self, result: Dict[str, Any]):
        """Update stats from result"""
        self.queries_processed += 1
        self.total_latency_ms += result.get('total_latency_ms', 0)

        for agent in result.get('executed_agents', []):
            self.agent_usage[agent] = self.agent_usage.get(agent, 0) + 1

        if result.get('error'):
            self.errors += 1

    def print_stats(self):
        """Print statistics"""
        print(f"\n{Colors.HEADER}{Colors.BOLD}{'='*70}")
        print(f"  {EMOJI['session']} SESSION STATISTICS")
        print(f"{'='*70}{Colors.ENDC}\n")

        print(f"{Colors.BOLD}Queries Processed:{Colors.ENDC} {self.queries_processed}")
        if self.queries_processed > 0:
            avg_latency = self.total_latency_ms / self.queries_processed
            print(f"{Colors.BOLD}Average Latency:{Colors.ENDC} {avg_latency:.0f}ms")

        if self.agent_usage:
            print(f"\n{Colors.BOLD}Agent Usage:{Colors.ENDC}")
            for agent, count in sorted(self.agent_usage.items(), key=lambda x: -x[1]):
                agent_emoji = EMOJI.get(agent.replace('_agent', ''), '🤖')
                print(f"  {agent_emoji} {agent}: {count} times")

        if self.errors > 0:
            print(f"\n{Colors.FAIL}Errors: {self.errors}{Colors.ENDC}")

        print()

def print_banner():
    """Print welcome banner"""
    print(f"\n{Colors.HEADER}{Colors.BOLD}{'='*70}")
    print(f"  {EMOJI['thinking']} KrishiMitra - Supervisor V2 Interactive Test")
    print(f"{'='*70}{Colors.ENDC}\n")
    print(f"{Colors.OKCYAN}Welcome to the comprehensive Supervisor V2 test interface!")
    print(f"This tool lets you test all agents with detailed query flow insights.{Colors.ENDC}\n")
    print(f"{Colors.DIM}Type 'help' for examples, 'debug' for details, 'quit' to exit.{Colors.ENDC}\n")

def print_help():
    """Print comprehensive help with examples for all agents"""
    print(f"\n{Colors.HEADER}{Colors.BOLD}{'='*70}")
    print(f"  EXAMPLE QUERIES")
    print(f"{'='*70}{Colors.ENDC}\n")

    categories = {
        f"{EMOJI['crop']} Crop Recommendation": [
            "What crops grow well in Maharashtra?",
            "Best crop for black soil with pH 7.5 and temperature 28C?",
            "Which crop should I plant in loamy soil?",
            "Sandy soil, N=40, P=50, K=30, temp=25C, humidity=60%. Recommend crop."
        ],
        f"{EMOJI['fertilizer']} Fertilizer Advice": [
            "What fertilizer for wheat in sandy soil?",
            "Which fertilizer should I use?",
            "Black soil, sugarcane crop, temperature 30C. Fertilizer recommendation?",
            "I need fertilizer for rice in loamy soil with high humidity"
        ],
        f"{EMOJI['weather']} Weather Information": [
            "What is the weather in Bangalore?",
            "Weather forecast for Mumbai?",
            "Tell me about the climate in Delhi",
            "Current weather conditions in Pune"
        ],
        f"{EMOJI['disease']} Disease Detection": [
            "My tomato leaves have brown spots",
            "Is my crop healthy? (with image upload)",
            "Plant disease identification",
            "Crop health diagnosis"
        ],
        f"{EMOJI['rag']} General Agriculture Knowledge": [
            "What is crop rotation?",
            "Best practices for organic farming",
            "How to improve soil health?",
            "Tell me about drip irrigation"
        ],
        f"{EMOJI['thinking']} Multi-Agent Queries": [
            "What crops grow in Bangalore and what's the weather like?",
            "Best crop for my soil and which fertilizer to use?",
            "Weather in Mumbai and suitable crops for the region"
        ]
    }

    for category, examples in categories.items():
        print(f"{Colors.BOLD}{category}{Colors.ENDC}")
        for example in examples:
            print(f"  {Colors.OKGREEN}• {example}{Colors.ENDC}")
        print()

def print_examples_for_agent(agent: str):
    """Print examples for specific agent"""
    examples_map = {
        'crop': [
            "What crops grow well in Maharashtra?",
            "Best crop for black soil with pH 7.5?",
            "Sandy soil, N=40, P=50, K=30. Recommend crop."
        ],
        'fertilizer': [
            "What fertilizer for wheat in sandy soil?",
            "Which fertilizer should I use?",
            "Fertilizer recommendation for rice?"
        ],
        'weather': [
            "What is the weather in Bangalore?",
            "Weather forecast for Mumbai?",
            "Current weather conditions in Pune"
        ],
        'disease': [
            "My tomato leaves have brown spots",
            "Is my crop healthy?",
            "Plant disease identification"
        ],
        'rag': [
            "What is crop rotation?",
            "Best practices for organic farming",
            "How to improve soil health?"
        ]
    }

    if agent.lower() in examples_map:
        emoji = EMOJI.get(agent.lower(), '🤖')
        print(f"\n{Colors.BOLD}{emoji} {agent.upper()} Agent Examples:{Colors.ENDC}")
        for example in examples_map[agent.lower()]:
            print(f"  {Colors.OKGREEN}• {example}{Colors.ENDC}")
        print()
    else:
        print(f"{Colors.WARNING}Unknown agent. Try: crop, fertilizer, weather, disease, rag{Colors.ENDC}\n")

def print_separator():
    """Print separator line"""
    print(f"{Colors.OKBLUE}{'─'*70}{Colors.ENDC}")

def format_query_flow_insights(result: Dict[str, Any]) -> str:
    """Generate detailed query flow insights"""
    insights = []

    # Classification insight
    intent = result.get('intent', 'unknown')
    executed_agents = result.get('executed_agents', [])

    if len(executed_agents) == 1:
        agent = executed_agents[0]
        agent_type = agent.replace('_agent', '')
        emoji = EMOJI.get(agent_type, '🤖')
        insights.append(f"{emoji} Classified as {Colors.BOLD}{intent}{Colors.ENDC} → routed to {Colors.OKCYAN}{agent}{Colors.ENDC}")
    elif len(executed_agents) > 1:
        agents_str = " → ".join(executed_agents)
        insights.append(f"{EMOJI['thinking']} Multi-agent query → {Colors.OKCYAN}{agents_str}{Colors.ENDC}")

    # Session insight
    session_id = result.get('session_id', 'N/A')
    turn_count = result.get('turn_count', 0)
    if turn_count > 1:
        insights.append(f"{EMOJI['session']} Multi-turn conversation (Turn {turn_count}, Session: {session_id[:8]}...)")
    else:
        insights.append(f"{EMOJI['session']} New session created: {session_id[:8]}...")

    # Performance insight
    latency = result.get('total_latency_ms', 0)
    if latency > 5000:
        insights.append(f"{EMOJI['latency']} High latency: {latency:.0f}ms - consider optimization")
    elif latency > 2000:
        insights.append(f"{EMOJI['latency']} Moderate latency: {latency:.0f}ms")
    else:
        insights.append(f"{EMOJI['latency']} Fast response: {latency:.0f}ms")

    # Agent-specific insights
    collected_findings = result.get('collected_findings', {})
    for agent_name, finding in collected_findings.items():
        status = finding.get('status', 'unknown')
        if status == 'needs_clarification':
            missing = finding.get('missing_fields', [])
            insights.append(f"{EMOJI['clarification']} {agent_name} needs clarification: {', '.join(missing)}")
        elif status == 'success':
            data = finding.get('data', {})
            # Add specific insights per agent
            if 'crop' in agent_name:
                crop = data.get('recommended_crop', 'N/A')
                confidence = data.get('confidence_percentage', 0)
                insights.append(f"{EMOJI['crop']} Recommended: {crop} ({confidence:.0f}% confidence)")
            elif 'weather' in agent_name:
                temp = data.get('temperature', 'N/A')
                humidity = data.get('humidity', 'N/A')
                insights.append(f"{EMOJI['weather']} Conditions: {temp}°C, {humidity}% humidity")

    return "\n".join(f"  {Colors.DIM}→{Colors.ENDC} {insight}" for insight in insights)

def format_collected_findings(collected_findings: Dict[str, Any]) -> str:
    """Format collected findings for debug mode"""
    if not collected_findings:
        return f"{Colors.DIM}No findings collected{Colors.ENDC}"

    output = []
    for agent_name, finding in collected_findings.items():
        status = finding.get('status', 'unknown')
        status_emoji = {
            'success': EMOJI['success'],
            'error': EMOJI['error'],
            'needs_clarification': EMOJI['clarification']
        }.get(status, '⚠️')

        output.append(f"\n  {status_emoji} {Colors.BOLD}{agent_name}{Colors.ENDC} ({status})")

        if status == 'success':
            data = finding.get('data', {})
            for key, value in list(data.items())[:5]:  # Show first 5 fields
                value_str = str(value)[:60]  # Truncate long values
                output.append(f"      {Colors.DIM}{key}:{Colors.ENDC} {value_str}")
        elif status == 'error':
            error = finding.get('error', 'Unknown error')
            output.append(f"      {Colors.FAIL}{error}{Colors.ENDC}")
        elif status == 'needs_clarification':
            missing = finding.get('missing_fields', [])
            question = finding.get('clarification_question', '')
            if question:
                output.append(f"      {Colors.WARNING}{question}{Colors.ENDC}")
            if missing:
                output.append(f"      {Colors.DIM}Missing: {', '.join(missing)}{Colors.ENDC}")

    return "\n".join(output)

def format_result(result: Dict[str, Any], show_debug: bool = False):
    """Format and print comprehensive result"""
    print_separator()

    # Header
    print(f"\n{Colors.BOLD}{Colors.HEADER}RESPONSE{Colors.ENDC}\n")

    # Query Flow Insights
    print(f"{Colors.BOLD}Query Flow Insights:{Colors.ENDC}")
    print(format_query_flow_insights(result))
    print()

    # Answer
    answer = result.get('final_response') or result.get('answer', 'No answer generated')
    print(f"{Colors.BOLD}Answer:{Colors.ENDC}")
    print(f"{Colors.OKGREEN}{answer}{Colors.ENDC}")
    print()

    # Debug information
    if show_debug:
        print(f"{Colors.BOLD}{Colors.WARNING}DEBUG INFORMATION{Colors.ENDC}")

        # Collected findings
        collected_findings = result.get('collected_findings', {})
        print(f"\n{Colors.BOLD}Collected Findings:{Colors.ENDC}")
        print(format_collected_findings(collected_findings))

        # Node latencies
        node_latencies = result.get('node_latencies', {})
        if node_latencies:
            print(f"\n{Colors.BOLD}Node Latencies:{Colors.ENDC}")
            for node, latency in node_latencies.items():
                print(f"  {Colors.DIM}•{Colors.ENDC} {node}: {latency:.0f}ms")

        # Session details
        print(f"\n{Colors.BOLD}Session Details:{Colors.ENDC}")
        print(f"  {Colors.DIM}•{Colors.ENDC} Session ID: {result.get('session_id', 'N/A')}")
        print(f"  {Colors.DIM}•{Colors.ENDC} Turn: {result.get('turn_count', 'N/A')}")
        print(f"  {Colors.DIM}•{Colors.ENDC} Active: {result.get('is_active', 'N/A')}")
        print()

    print_separator()
    print()

def print_session_info(session_id: str, turn_count: int):
    """Print current session information"""
    print(f"\n{Colors.HEADER}{Colors.BOLD}CURRENT SESSION{Colors.ENDC}")
    print(f"{Colors.DIM}Session ID:{Colors.ENDC} {session_id or 'None (will create new session)'}")
    print(f"{Colors.DIM}Turn Count:{Colors.ENDC} {turn_count}")
    print()

def test_query(query: str, session_id: str = None, show_debug: bool = False) -> Dict[str, Any]:
    """Test a single query"""
    try:
        print(f"{Colors.DIM}Processing query...{Colors.ENDC}\n")

        result = orchestrator.run(
            query=query,
            user_context={},
            images=None,
            session_id=session_id
        )

        format_result(result, show_debug=show_debug)

        return result

    except Exception as e:
        print(f"{Colors.FAIL}{Colors.BOLD}Error: {e}{Colors.ENDC}")
        if show_debug:
            import traceback
            traceback.print_exc()
        return {'error': str(e)}

def main():
    """Main interactive loop"""
    print_banner()

    # Initialize orchestrator (already initialized as singleton)
    print(f"{Colors.OKCYAN}Checking orchestrator health...{Colors.ENDC}")
    try:
        health = orchestrator.health_check()
        print(f"{Colors.OKGREEN}{EMOJI['success']} Orchestrator ready!{Colors.ENDC}\n")

        # Show health details
        print(f"{Colors.DIM}Health Check:{Colors.ENDC}")
        print(f"  {Colors.DIM}•{Colors.ENDC} Status: {health.get('status', 'unknown')}")
        agents_avail = health.get('agents_available', {})
        if agents_avail:
            available = sum(1 for v in agents_avail.values() if v)
            total = len(agents_avail)
            print(f"  {Colors.DIM}•{Colors.ENDC} Agents: {available}/{total} available")
        print()

    except Exception as e:
        print(f"{Colors.FAIL}Failed to check orchestrator: {e}{Colors.ENDC}")
        print(f"{Colors.WARNING}Continuing anyway...{Colors.ENDC}\n")

    # Session state
    current_session_id = None
    turn_count = 0
    show_debug = False
    stats = SessionStats()

    # Interactive loop
    while True:
        try:
            # Get user input
            query = input(f"{Colors.BOLD}Your query:{Colors.ENDC} ").strip()

            # Handle special commands
            if query.lower() in ['quit', 'exit', 'q']:
                print(f"\n{Colors.OKCYAN}Thanks for testing! Goodbye! {EMOJI['success']}{Colors.ENDC}\n")
                break

            elif query.lower() == 'help':
                print_help()
                continue

            elif query.lower().startswith('examples'):
                parts = query.split()
                if len(parts) > 1:
                    print_examples_for_agent(parts[1])
                else:
                    print_help()
                continue

            elif query.lower() == 'debug':
                show_debug = not show_debug
                status = "enabled" if show_debug else "disabled"
                print(f"{Colors.WARNING}Debug mode {status}{Colors.ENDC}\n")
                continue

            elif query.lower() == 'session':
                print_session_info(current_session_id, turn_count)
                continue

            elif query.lower() == 'reset':
                current_session_id = None
                turn_count = 0
                print(f"{Colors.WARNING}Session reset! Next query will start a new conversation.{Colors.ENDC}\n")
                continue

            elif query.lower() == 'stats':
                stats.print_stats()
                continue

            elif not query:
                continue

            # Process query
            result = test_query(query, session_id=current_session_id, show_debug=show_debug)

            # Update session state
            if 'session_id' in result:
                current_session_id = result['session_id']
                turn_count = result.get('turn_count', turn_count)

            # Update statistics
            stats.update(result)

        except KeyboardInterrupt:
            print(f"\n\n{Colors.OKCYAN}Interrupted. Type 'quit' to exit.{Colors.ENDC}\n")
        except Exception as e:
            print(f"{Colors.FAIL}Error: {e}{Colors.ENDC}\n")
            if show_debug:
                import traceback
                traceback.print_exc()

if __name__ == "__main__":
    main()
